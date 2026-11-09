"""Proyectos y capítulos de Text Studio. Autocontenido: abre su propia conexión SQLite."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Callable

from .importers import extract_text, ImporterError

_NAME_RE = re.compile(r"^[\w-]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    voice_profile TEXT NOT NULL,
    language      TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS chapters (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    ordinal     INTEGER NOT NULL,
    title       TEXT NOT NULL,
    source_path TEXT,
    text        TEXT NOT NULL,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_chapters_project ON chapters(project_id, ordinal);
"""


class ProjectError(RuntimeError):
    pass


class ProjectNotFound(ProjectError):
    pass


class ChapterNotFound(ProjectError):
    pass


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(_SCHEMA)
    return conn


def _chapter_count(conn: sqlite3.Connection, project_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM chapters WHERE project_id = ?", (project_id,)
    ).fetchone()
    return row["n"] if row else 0


def _get_project_row(conn: sqlite3.Connection, name: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise ProjectNotFound(f"No existe el proyecto '{name}'.")
    return row


def create_project(db_path: Path, name: str, voice: str, language: str | None) -> dict:
    if not _NAME_RE.match(name):
        raise ProjectError(
            "El nombre del proyecto solo admite letras, números, guiones y guion bajo."
        )
    conn = _connect(db_path)
    try:
        if conn.execute("SELECT 1 FROM projects WHERE name = ?", (name,)).fetchone():
            raise ProjectError(f"Ya existe un proyecto llamado '{name}'.")
        cur = conn.execute(
            "INSERT INTO projects (name, voice_profile, language) VALUES (?, ?, ?)",
            (name, voice, language),
        )
        conn.commit()
        return {
            "id": cur.lastrowid,
            "name": name,
            "voice_profile": voice,
            "language": language,
            "chapters": 0,
        }
    finally:
        conn.close()


def list_projects(db_path: Path) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.name, p.voice_profile, p.language,
                   (SELECT COUNT(*) FROM chapters c WHERE c.project_id = p.id) AS chapters
            FROM projects p
            ORDER BY p.name
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_project(db_path: Path, name: str) -> dict:
    conn = _connect(db_path)
    try:
        row = _get_project_row(conn, name)
        d = dict(row)
        d["chapters"] = _chapter_count(conn, row["id"])
        return d
    finally:
        conn.close()


def delete_project(db_path: Path, name: str, *, yes: bool = False) -> dict:
    conn = _connect(db_path)
    try:
        row = _get_project_row(conn, name)
        n_chapters = _chapter_count(conn, row["id"])
        plan = {
            "project": name,
            "voice_profile": row["voice_profile"],
            "chapters_to_delete": n_chapters,
            "touches_voices": False,
            "touches_global_cache": False,
        }
        if not yes:
            plan["dry_run"] = True
            return plan
        conn.execute("DELETE FROM projects WHERE id = ?", (row["id"],))
        conn.commit()
        plan["dry_run"] = False
        plan["deleted_chapters"] = n_chapters
        return plan
    finally:
        conn.close()


def add_chapter(
    db_path: Path,
    project_name: str,
    title: str,
    file_path: Path,
    lang: str = "spa",
    *,
    log: Callable[[str], None] | None = None,
) -> dict:
    if not title.strip():
        raise ProjectError("El título del capítulo no puede estar vacío.")
    conn = _connect(db_path)
    try:
        prow = _get_project_row(conn, project_name)
        try:
            text = extract_text(file_path, lang=lang, log=log)
        except ImporterError as exc:
            raise ProjectError(f"No se pudo importar el capítulo: {exc}") from exc
        if not text.strip():
            raise ProjectError("El texto extraído está vacío.")
        ordinal = conn.execute(
            "SELECT COALESCE(MAX(ordinal), 0) + 1 AS nx FROM chapters WHERE project_id = ?",
            (prow["id"],),
        ).fetchone()["nx"]
        cur = conn.execute(
            """
            INSERT INTO chapters (project_id, ordinal, title, source_path, text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (prow["id"], ordinal, title.strip(), str(file_path), text),
        )
        conn.commit()
        return {
            "id": cur.lastrowid,
            "project": project_name,
            "ordinal": ordinal,
            "title": title.strip(),
            "source_path": str(file_path),
            "chars": len(text),
        }
    finally:
        conn.close()


def list_chapters(db_path: Path, project_name: str) -> list[dict]:
    conn = _connect(db_path)
    try:
        prow = _get_project_row(conn, project_name)
        rows = conn.execute(
            """
            SELECT ordinal, title, source_path, LENGTH(text) AS chars, created_at
            FROM chapters WHERE project_id = ?
            ORDER BY ordinal
            """,
            (prow["id"],),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_chapter(db_path: Path, project_name: str, ordinal: int) -> dict:
    conn = _connect(db_path)
    try:
        prow = _get_project_row(conn, project_name)
        row = conn.execute(
            "SELECT * FROM chapters WHERE project_id = ? AND ordinal = ?",
            (prow["id"], ordinal),
        ).fetchone()
        if row is None:
            raise ChapterNotFound(
                f"El proyecto '{project_name}' no tiene el capítulo {ordinal}."
            )
        return dict(row)
    finally:
        conn.close()


def update_chapter(
    db_path: Path,
    project_name: str,
    ordinal: int,
    *,
    title: str | None = None,
    text: str | None = None,
) -> dict:
    """Actualiza el título y/o el texto de un capítulo existente."""
    if title is not None and not title.strip():
        raise ProjectError("El título del capítulo no puede estar vacío.")
    if text is not None and not text.strip():
        raise ProjectError("El texto del capítulo no puede estar vacío.")

    conn = _connect(db_path)
    try:
        prow = _get_project_row(conn, project_name)
        row = conn.execute(
            "SELECT id, title, text FROM chapters WHERE project_id = ? AND ordinal = ?",
            (prow["id"], ordinal),
        ).fetchone()
        if row is None:
            raise ChapterNotFound(
                f"El proyecto '{project_name}' no tiene el capítulo {ordinal}."
            )

        new_title = row["title"] if title is None else title.strip()
        new_text = row["text"] if text is None else text
        conn.execute(
            "UPDATE chapters SET title = ?, text = ? WHERE id = ?",
            (new_title, new_text, row["id"]),
        )
        conn.commit()
        return {
            "id": row["id"],
            "project": project_name,
            "ordinal": ordinal,
            "title": new_title,
            "chars": len(new_text),
        }
    finally:
        conn.close()


def list_chapters_full(db_path: Path, project_name: str) -> list[dict]:
    """Capítulos con texto, en orden. Para narración por proyecto."""
    conn = _connect(db_path)
    try:
        prow = _get_project_row(conn, project_name)
        rows = conn.execute(
            """
            SELECT ordinal, title, text
            FROM chapters WHERE project_id = ?
            ORDER BY ordinal
            """,
            (prow["id"],),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()