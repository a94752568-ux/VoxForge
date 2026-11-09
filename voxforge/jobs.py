"""Trabajos en segundo plano para producción de VoxForge."""
from __future__ import annotations

import json
import os
import signal
import sqlite3
import time
from pathlib import Path
from typing import Any


JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    name TEXT,
    kind TEXT NOT NULL,
    project TEXT,
    ordinal INTEGER,
    command TEXT NOT NULL,
    cwd TEXT NOT NULL,
    log_path TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    pid INTEGER,
    pgid INTEGER,
    child_pid INTEGER,
    started_at TEXT,
    finished_at TEXT,
    exit_code INTEGER,
    note TEXT,
    meta TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project, ordinal);
"""


class JobError(RuntimeError):
    pass


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _iso_from_epoch(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    return True


def _decode_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


class JobStore:
    ACTIVE_STATUSES = ("pending", "running")
    FINISHED_STATUSES = ("succeeded", "failed", "canceled", "lost")

    def __init__(self, db_path: Path, data_dir: Path) -> None:
        self.db_path = Path(db_path)
        self.data_dir = Path(data_dir)
        self.jobs_dir = self.data_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.executescript(JOBS_SCHEMA)
        return conn

    def create_job(
        self,
        *,
        kind: str,
        command: list[str],
        cwd: str,
        name: str | None = None,
        project: str | None = None,
        ordinal: int | None = None,
        meta: dict | None = None,
    ) -> tuple[int, Path]:
        conn = self._conn()
        try:
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    name, kind, project, ordinal, command, cwd,
                    log_path, status, meta
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    name,
                    kind,
                    project,
                    ordinal,
                    json.dumps(command, ensure_ascii=False),
                    cwd,
                    "",
                    json.dumps(meta or {}, ensure_ascii=False),
                ),
            )
            job_id = int(cur.lastrowid)
            log_path = self.jobs_dir / f"{job_id:05d}.log"
            conn.execute(
                "UPDATE jobs SET log_path = ? WHERE id = ?",
                (str(log_path), job_id),
            )
            conn.commit()
            return job_id, log_path
        finally:
            conn.close()

    def get_job(self, job_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_jobs(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
        project: str | None = None,
    ) -> list[dict]:
        self.reap_stale()

        conn = self._conn()
        try:
            q = "SELECT * FROM jobs"
            params: list[Any] = []
            wheres: list[str] = []

            if status:
                wheres.append("status = ?")
                params.append(status)

            if project:
                wheres.append("project = ?")
                params.append(project)

            if wheres:
                q += " WHERE " + " AND ".join(wheres)

            q += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def active_jobs(
        self,
        *,
        project: str | None = None,
        ordinal: int | None = None,
        kind: str | None = None,
    ) -> list[dict]:
        self.reap_stale()

        conn = self._conn()
        try:
            q = "SELECT * FROM jobs WHERE status IN (?, ?)"
            params: list[Any] = list(self.ACTIVE_STATUSES)

            if project is not None:
                q += " AND project = ?"
                params.append(project)

            if ordinal is not None:
                q += " AND ordinal = ?"
                params.append(ordinal)

            if kind:
                q += " AND kind = ?"
                params.append(kind)

            q += " ORDER BY id DESC"
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def mark_running(self, job_id: int, pid: int, pgid: int | None = None) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'running',
                    pid = ?,
                    pgid = ?,
                    started_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (pid, pgid, _utcnow(), job_id),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_child_pid(self, job_id: int, child_pid: int) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE jobs SET child_pid = ? WHERE id = ?",
                (child_pid, job_id),
            )
            conn.commit()
        finally:
            conn.close()

    def finish(
        self,
        job_id: int,
        status: str,
        exit_code: int | None = None,
        note: str = "",
    ) -> bool:
        conn = self._conn()
        try:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    exit_code = ?,
                    finished_at = ?,
                    note = ?
                WHERE id = ? AND status IN ('pending', 'running')
                """,
                (status, exit_code, _utcnow(), note, job_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def cancel(self, job_id: int) -> bool:
        job = self.get_job(job_id)
        if job is None:
            raise JobError(f"No existe el trabajo {job_id}.")

        if job["status"] not in self.ACTIVE_STATUSES:
            return False

        pid = job.get("pid") or job.get("child_pid")
        pgid = job.get("pgid")

        if pid:
            try:
                if pgid:
                    os.killpg(int(pgid), signal.SIGTERM)
                else:
                    os.killpg(os.getpgid(int(pid)), signal.SIGTERM)
            except Exception:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except Exception:
                    pass

        return self.finish(job_id, "canceled", None, "cancelado por usuario")

    def reap_stale(self) -> None:
        """Marca como perdidos los trabajos running cuyo proceso ya no existe."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, pid, child_pid FROM jobs WHERE status = 'running'"
            ).fetchall()

            now = _utcnow()
            for row in rows:
                pid = row["pid"] or row["child_pid"]
                if not _pid_alive(pid):
                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = 'lost',
                            finished_at = ?,
                            note = ?
                        WHERE id = ? AND status = 'running'
                        """,
                        (now, "proceso runner no encontrado", row["id"]),
                    )
            conn.commit()
        finally:
            conn.close()

    def delete_finished(
        self,
        *,
        older_than_days: float | None = None,
    ) -> int:
        self.reap_stale()

        conn = self._conn()
        try:
            q = "SELECT id, log_path FROM jobs WHERE status IN ({})".format(
                ",".join("?" for _ in self.FINISHED_STATUSES)
            )
            params: list[Any] = list(self.FINISHED_STATUSES)

            if older_than_days is not None:
                cutoff = _iso_from_epoch(time.time() - older_than_days * 86400)
                q += " AND finished_at IS NOT NULL AND finished_at < ?"
                params.append(cutoff)

            rows = conn.execute(q, params).fetchall()
            ids: list[int] = []

            for row in rows:
                job_id = int(row["id"])
                ids.append(job_id)

                log_path = row["log_path"]
                if log_path:
                    try:
                        Path(log_path).unlink(missing_ok=True)
                    except Exception:
                        pass

            if not ids:
                return 0

            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"DELETE FROM jobs WHERE id IN ({placeholders})",
                ids,
            )
            conn.commit()
            return len(ids)
        finally:
            conn.close()