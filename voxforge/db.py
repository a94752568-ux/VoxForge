"""Base de datos SQLite: perfiles de voz y caché de fragmentos generados."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_profiles (
    id         INTEGER PRIMARY KEY,
    name       TEXT UNIQUE NOT NULL,
    ref_path   TEXT NOT NULL,
    ref_sha256 TEXT NOT NULL,
    language   TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fragments (
    hash       TEXT PRIMARY KEY,
    engine     TEXT NOT NULL,
    profile_id INTEGER NOT NULL REFERENCES voice_profiles(id),
    text       TEXT NOT NULL,
    path       TEXT NOT NULL,
    audio_s    REAL NOT NULL,
    compute_s  REAL NOT NULL,
    created_at TEXT NOT NULL,
    attempt    INTEGER NOT NULL DEFAULT 0,
    ok         INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS project_progress (
    project_name TEXT NOT NULL,
    chapter_id   INTEGER NOT NULL,
    total_fragments INTEGER NOT NULL DEFAULT 0,
    processed_fragments INTEGER NOT NULL DEFAULT 0,
    current_fragment INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT,
    last_update TEXT,
    finished_at TEXT,
    error_message TEXT,
    PRIMARY KEY (project_name, chapter_id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Añade columnas nuevas a bases de datos creadas con versiones anteriores."""
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(fragments)")}
        with self.conn:
            if "attempt" not in cols:
                self.conn.execute("ALTER TABLE fragments ADD COLUMN attempt INTEGER NOT NULL DEFAULT 0")
            if "ok" not in cols:
                self.conn.execute("ALTER TABLE fragments ADD COLUMN ok INTEGER NOT NULL DEFAULT 1")

    def close(self) -> None:
        self.conn.close()

    # --- perfiles de voz ---
    def add_profile(self, name: str, ref_path: Path, ref_sha256: str, language: str) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO voice_profiles(name, ref_path, ref_sha256, language, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, str(ref_path), ref_sha256, language, _now()),
            )
        return int(cur.lastrowid)

    def get_profile(self, name: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM voice_profiles WHERE name = ?", (name,)).fetchone()

    def list_profiles(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM voice_profiles ORDER BY name").fetchall()

    # --- caché de fragmentos ---
    def get_fragment(self, digest: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM fragments WHERE hash = ?", (digest,)).fetchone()

    def add_fragment(self, digest: str, engine: str, profile_id: int, text: str,
                     path: Path, audio_s: float, compute_s: float,
                     attempt: int = 0, ok: bool = True) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO fragments(hash, engine, profile_id, text, path, audio_s, "
                "compute_s, created_at, attempt, ok) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (digest, engine, profile_id, text, str(path), audio_s, compute_s, _now(),
                 attempt, int(ok)),
            )

    def fragment_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM fragments").fetchone()[0])

    # --- progreso de proyectos ---
    def get_project_progress(self, project_name: str, chapter_id: int) -> sqlite3.Row | None:
        """Obtiene el progreso de narración de un capítulo."""
        return self.conn.execute(
            "SELECT * FROM project_progress WHERE project_name = ? AND chapter_id = ?",
            (project_name, chapter_id)
        ).fetchone()

    def update_project_progress(
        self,
        project_name: str,
        chapter_id: int,
        total_fragments: int,
        processed_fragments: int,
        current_fragment: int,
        status: str,
        started_at: str | None = None,
        finished_at: str | None = None,
        error_message: str | None = None
    ) -> None:
        """Actualiza el progreso de narración de un capítulo.
        
        Args:
            project_name: Nombre del proyecto.
            chapter_id: ID del capítulo.
            total_fragments: Total de fragmentos a procesar.
            processed_fragments: Fragmentos ya procesados.
            current_fragment: Fragmento actual (para reanudación).
            status: Estado (pending, running, completed, failed, cancelled).
            started_at: Fecha de inicio (ISO format).
            finished_at: Fecha de finalización (ISO format).
            error_message: Mensaje de error si status es 'failed'.
        """
        now = _now()
        with self.conn:
            existing = self.get_project_progress(project_name, chapter_id)
            if existing:
                self.conn.execute(
                    """UPDATE project_progress SET
                       total_fragments = ?,
                       processed_fragments = ?,
                       current_fragment = ?,
                       status = ?,
                       last_update = ?,
                       finished_at = ?,
                       error_message = ?
                       WHERE project_name = ? AND chapter_id = ?""",
                    (
                        total_fragments,
                        processed_fragments,
                        current_fragment,
                        status,
                        now,
                        finished_at,
                        error_message,
                        project_name,
                        chapter_id
                    )
                )
            else:
                self.conn.execute(
                    """INSERT INTO project_progress
                       (project_name, chapter_id, total_fragments, processed_fragments,
                        current_fragment, status, started_at, last_update, finished_at, error_message)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        project_name,
                        chapter_id,
                        total_fragments,
                        processed_fragments,
                        current_fragment,
                        status,
                        started_at or now,
                        now,
                        finished_at,
                        error_message
                    )
                )

    def clear_project_progress(self, project_name: str, chapter_id: int) -> None:
        """Elimina el progreso de un capítulo (útil para forzar regeneración)."""
        with self.conn:
            self.conn.execute(
                "DELETE FROM project_progress WHERE project_name = ? AND chapter_id = ?",
                (project_name, chapter_id)
            )
