# voxforge/voice_delete.py
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "voxforge.db"
VOICES_DIR = DATA_DIR / "voices"
SAMPLES_DIR = DATA_DIR / "samples"


class ProfileNotFound(RuntimeError):
    pass


def _ident(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Identificador SQL no seguro: {name}")
    return f'"{name}"'


def _tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [
        r[1]
        for r in conn.execute(f"PRAGMA table_info({_ident(table)})").fetchall()
    ]


def _is_related_table(table: str) -> bool:
    t = table.lower()
    return any(
        key in t
        for key in (
            "cache",
            "fragment",
            "voice",
            "sample",
            "profile",
            "version",
            "audio",
        )
    )


def _find_profile_table(conn: sqlite3.Connection) -> str:
    tables = set(_tables(conn))

    for cand in ("profiles", "voices", "voice_profiles", "voice_profile", "profile"):
        if cand in tables:
            return cand

    # Fallback: una tabla que tenga nombre y alguna ruta.
    for t in tables:
        cols = _columns(conn, t)
        has_name = any(c in cols for c in ("name", "profile_name", "voice_name"))
        has_path = any(c.endswith("_path") or c == "path" for c in cols)
        if has_name and has_path:
            return t

    raise RuntimeError("No se encontró la tabla de perfiles.")


def _resolve_path(value: str | os.PathLike[str]) -> Path:
    p = Path(str(value)).expanduser()

    if p.is_absolute():
        return p

    candidates = [
        ROOT / p,
        DATA_DIR / p,
        Path.cwd() / p,
    ]

    for c in candidates:
        if c.exists():
            return c

    return ROOT / p


def _sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _is_path_column(col: str) -> bool:
    return col.endswith("_path") or col in {
        "path",
        "file",
        "filename",
        "filepath",
    }


def _extract_paths(row: sqlite3.Row, out: set[Path]) -> None:
    for col in row.keys():
        if _is_path_column(col):
            val = row[col]
            if val:
                out.add(_resolve_path(val))


def _secure_unlink(path: Path, shred: bool = False) -> bool:
    if not path.exists() and not path.is_symlink():
        return False

    if path.is_dir():
        changed = False

        for child in sorted(path.iterdir(), reverse=True):
            changed |= _secure_unlink(child, shred)

        try:
            path.rmdir()
            return True
        except OSError:
            return changed

    if shred:
        try:
            size = path.stat().st_size
            if size > 0:
                with open(path, "r+b") as f:
                    chunk = 1024 * 1024
                    remaining = size

                    while remaining > 0:
                        block = b"\0" * min(chunk, remaining)
                        f.write(block)
                        remaining -= len(block)

                    f.flush()
                    os.fsync(f.fileno())
        except OSError:
            pass

    try:
        path.unlink()
        return True
    except OSError:
        return False


def _where_for_table(
    table: str,
    cols: list[str],
    *,
    profile_id: Any,
    name: str,
    ref_hash: str | None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if profile_id is not None and "profile_id" in cols:
        clauses.append("profile_id = ?")
        params.append(profile_id)

    for col in ("voice_name", "voice", "profile_name", "profile"):
        if col in cols:
            clauses.append(f"{_ident(col)} = ?")
            params.append(name)

    if "name" in cols:
        clauses.append(f"{_ident('name')} = ?")
        params.append(name)

    if ref_hash:
        for col in (
            "sample_hash",
            "ref_sha256",
            "reference_hash",
            "voice_hash",
            "ref_hash",
        ):
            if col in cols:
                clauses.append(f"{_ident(col)} = ?")
                params.append(ref_hash)

    if not clauses:
        return "", []

    return " OR ".join(clauses), params


def delete_voice(
    name: str,
    *,
    yes: bool = False,
    purge_source: bool = False,
    shred: bool = False,
    db_path: Path = DB_PATH,
) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    if yes:
        conn.execute("PRAGMA secure_delete = ON;")

    profile_table = _find_profile_table(conn)
    pcols = _columns(conn, profile_table)

    name_col = next(
        (c for c in ("name", "profile_name", "voice_name") if c in pcols),
        None,
    )

    if not name_col:
        raise RuntimeError(f"La tabla {profile_table} no tiene columna de nombre.")

    row = conn.execute(
        f"SELECT * FROM {_ident(profile_table)} WHERE {_ident(name_col)} = ?",
        (name,),
    ).fetchone()

    if row is None:
        raise ProfileNotFound(f"No existe el perfil '{name}'.")

    profile_id = row["id"] if "id" in row.keys() else None

    files: set[Path] = set()
    _extract_paths(row, files)

    # Directorio estándar del perfil.
    files.add(VOICES_DIR / name)

    # Referencia principal.
    ref_path = None
    for c in ("ref_path", "reference_path", "voice_path", "sample_path"):
        if c in row.keys() and row[c]:
            ref_path = _resolve_path(row[c])
            break

    if ref_path is None:
        candidate = VOICES_DIR / name / "ref.wav"
        if candidate.exists():
            ref_path = candidate

    if ref_path:
        files.add(ref_path)

    ref_hash = _sha256(ref_path) if ref_path and ref_path.exists() else None

    if purge_source:
        for c in ("source_path", "original_path", "sample_path", "input_path"):
            if c in row.keys() and row[c]:
                files.add(_resolve_path(row[c]))

        # Búsqueda por convención en data/samples.
        for ext in (".wav", ".flac", ".mp3", ".ogg"):
            files.add(SAMPLES_DIR / f"{name}{ext}")

    related: dict[str, int] = {}
    related_files: set[Path] = set()

    for table in _tables(conn):
        if table == profile_table:
            continue

        if not _is_related_table(table):
            continue

        cols = _columns(conn, table)

        where, params = _where_for_table(
            table,
            cols,
            profile_id=profile_id,
            name=name,
            ref_hash=ref_hash,
        )

        if not where:
            continue

        rows = conn.execute(
            f"SELECT * FROM {_ident(table)} WHERE {where}",
            params,
        ).fetchall()

        related[table] = len(rows)

        for r in rows:
            _extract_paths(r, related_files)

    files.update(related_files)

    # Nunca borrar la propia base de datos.
    files = {f for f in files if f.resolve() != db_path.resolve()}

    plan = {
        "profile": name,
        "profile_table": profile_table,
        "db_rows_to_delete": related,
        "files_to_delete": sorted(str(f) for f in files if f.exists()),
        "ref_hash": ref_hash,
    }

    if not yes:
        plan["dry_run"] = True
        conn.close()
        return plan

    deleted: dict[str, int] = {}

    for table in _tables(conn):
        if table == profile_table:
            continue

        if not _is_related_table(table):
            continue

        cols = _columns(conn, table)

        where, params = _where_for_table(
            table,
            cols,
            profile_id=profile_id,
            name=name,
            ref_hash=ref_hash,
        )

        if not where:
            continue

        cur = conn.execute(
            f"DELETE FROM {_ident(table)} WHERE {where}",
            params,
        )

        deleted[table] = cur.rowcount

    cur = conn.execute(
        f"DELETE FROM {_ident(profile_table)} WHERE {_ident(name_col)} = ?",
        (name,),
    )

    deleted[profile_table] = cur.rowcount

    conn.commit()

    try:
        conn.execute("VACUUM;")
    except sqlite3.OperationalError:
        pass

    conn.close()

    removed_files = []

    for f in sorted(files):
        if f.exists() and _secure_unlink(f, shred=shred):
            removed_files.append(str(f))

    return {
        "profile": name,
        "profile_table": profile_table,
        "dry_run": False,
        "deleted_db_rows": deleted,
        "deleted_files": removed_files,
        "ref_hash": ref_hash,
    }