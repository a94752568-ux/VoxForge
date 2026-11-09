"""Importación de libros completos: extrae texto y crea partes/capítulos por tamaño."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .importers import extract_text

DEFAULT_TARGET_CHARS = 45000
DEFAULT_HARD_MAX_CHARS = 60000

_SENTENCE_END = re.compile(r"[.!?…](?=\s|$)")


class BookImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class BookPart:
    number: int
    path: Path
    chars: int
    minutes: float


def _validate_limits(target_chars: int, hard_max_chars: int) -> None:
    if target_chars <= 0:
        raise BookImportError("--target-chars debe ser mayor que 0.")
    if hard_max_chars <= 0:
        raise BookImportError("--hard-max-chars debe ser mayor que 0.")
    if hard_max_chars < target_chars:
        raise BookImportError(
            "--hard-max-chars no puede ser menor que --target-chars."
        )


def _split_huge_paragraph(paragraph: str, hard_max_chars: int) -> list[str]:
    """Parte un párrafo demasiado largo por frases, sin exceder hard_max_chars."""
    pieces: list[str] = []
    p = paragraph.strip()

    while len(p) > hard_max_chars:
        cut = None
        for m in _SENTENCE_END.finditer(p[:hard_max_chars]):
            cut = m.end()

        if cut is None or cut <= 0:
            cut = hard_max_chars

        piece = p[:cut].strip()
        p = p[cut:].strip()

        if piece:
            pieces.append(piece)

    if p:
        pieces.append(p)

    return pieces


def _pack_pieces(pieces: list[str], target_chars: int) -> list[str]:
    """Agrupa piezas consecutivas intentando no superar target_chars."""
    chunks: list[str] = []
    current = ""

    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue

        if not current:
            current = piece
            continue

        if len(current) + len(piece) + 2 > target_chars:
            chunks.append(current.strip())
            current = piece
        else:
            current = f"{current}\n\n{piece}"

    if current.strip():
        chunks.append(current.strip())

    return chunks


def split_book_text(
    text: str,
    target_chars: int = DEFAULT_TARGET_CHARS,
    hard_max_chars: int = DEFAULT_HARD_MAX_CHARS,
) -> list[str]:
    """Divide un texto largo en partes pensadas para capítulos de narración."""
    _validate_limits(target_chars, hard_max_chars)

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    pieces: list[str] = []

    for paragraph in paragraphs:
        if len(paragraph) > hard_max_chars:
            pieces.extend(_split_huge_paragraph(paragraph, hard_max_chars))
        else:
            pieces.append(paragraph)

    return _pack_pieces(pieces, target_chars)


def prepare_book_parts(
    source_path: Path,
    out_dir: Path,
    *,
    target_chars: int = DEFAULT_TARGET_CHARS,
    hard_max_chars: int = DEFAULT_HARD_MAX_CHARS,
    lang: str = "spa",
    log: Callable[[str], None] = print,
) -> list[BookPart]:
    """Extrae texto de un libro y escribe partes numeradas en out_dir."""
    _validate_limits(target_chars, hard_max_chars)

    if not source_path.is_file():
        raise BookImportError(f"No existe el archivo fuente: {source_path}")

    text = extract_text(source_path, lang=lang, log=log)

    if not text.strip():
        raise BookImportError("El archivo fuente no contiene texto extraíble.")

    parts_text = split_book_text(
        text,
        target_chars=target_chars,
        hard_max_chars=hard_max_chars,
    )

    if not parts_text:
        raise BookImportError("No se pudieron generar partes a partir del texto.")

    out_dir.mkdir(parents=True, exist_ok=True)

    parts: list[BookPart] = []

    for i, chunk in enumerate(parts_text, start=1):
        path = out_dir / f"{i:02d}.txt"
        path.write_text(chunk + "\n", encoding="utf-8")

        chars = len(chunk)
        minutes = chars / 10 / 60

        parts.append(
            BookPart(
                number=i,
                path=path,
                chars=chars,
                minutes=minutes,
            )
        )

        log(f"{path.name}: {chars} car. (~{minutes:.1f} min de audio estimado)")

    total_chars = sum(p.chars for p in parts)
    total_minutes = total_chars / 10 / 60

    log(
        f"\nTotal: {len(parts)} partes en {out_dir}/ "
        f"({total_chars} caracteres, ~{total_minutes:.1f} min de audio estimado)"
    )

    return parts