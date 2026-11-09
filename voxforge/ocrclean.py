"""Limpieza del texto reconocido por OCR para que se pueda narrar sin ruido.

Se aplica solo al texto que viene de OCR (nunca a TXT/MD ni a PDF con capa de
texto), porque asume que hay cortes de línea, folios y encabezados de página.

Qué hace:
- Une palabras cortadas por guion al final de línea (``Gua-\\ntemala``).
- Elimina los folios (números de página) del principio/fin de cada página,
  detectando el desplazamiento habitual entre el índice del PDF y el número
  impreso (p. ej. PDF 50 -> folio 52; desplazamiento +2), y también los números
  sueltos entre líneas en blanco (portadillas, páginas con ilustraciones).
- Elimina encabezados que se repiten en una gran parte de las páginas,
  conservando la primera aparición (que suele ser el título real).
- Elimina líneas decorativas sin texto (``|``, ``***``) en los bordes.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_LIGATURES = str.maketrans({
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
})
_SOFT_HYPHEN = "\u00ad"
_PAGE_NUMBER = re.compile(r"^[\s.\-–—]*(\d{1,3})[\s.\-–—]*$")
_NOISE = re.compile(r"^[^\wÁÉÍÓÚÜÑáéíóúüñ]+$")
_SENTENCE_END = re.compile(r"[.!?…:;]\s*$")
_HYPHEN_BREAK = re.compile(
    r"(?<=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])[-\u2010\u2011][ \t]*\n[ \t]*(?=[a-záéíóúüñ])"
)
_BLANK_LINES = re.compile(r"\n{3,}")

_HEADER_MAX_CHARS = 70
_HEADER_MIN_COUNT = 6
_HEADER_RATIO = 0.35
_FOLIO_MIN_COUNT = 3
_FOLIO_RATIO = 0.15


@dataclass(frozen=True)
class OcrCleanResult:
    """Texto limpio y contadores de lo que se ha eliminado/ajustado."""

    text: str
    hyphen_joins: int = 0
    page_numbers_removed: int = 0
    headers_removed: int = 0
    noise_lines_removed: int = 0


def _normalize_line(line: str) -> str:
    line = line.replace(_SOFT_HYPHEN, "").replace("\xa0", " ").translate(_LIGATURES)
    return re.sub(r"[ \t]+", " ", line).strip()


def _header_key(line: str) -> str:
    """Clave insensible a mayúsculas y a números para detectar repeticiones."""
    key = re.sub(r"\d+", "#", line.casefold())
    key = re.sub(r"[^\wáéíóúüñ#]+", " ", key)
    return re.sub(r"\s+", " ", key).strip()


def _header_candidate(line: str) -> str | None:
    """Devuelve la clave si la línea parece un encabezado, no un folio ni una frase."""
    if not line or len(line) > _HEADER_MAX_CHARS:
        return None
    if _PAGE_NUMBER.match(line) or _NOISE.match(line):
        return None
    if _SENTENCE_END.search(line):
        return None
    key = _header_key(line)
    if len(key) < 3 or key == "#":
        return None
    return key


def _boundary_indexes(lines: list[str]) -> set[int]:
    """Índices de las dos primeras y dos últimas líneas con contenido."""
    nonempty = [i for i, line in enumerate(lines) if line]
    if not nonempty:
        return set()
    return set(nonempty[:2] + nonempty[-2:])


def _page_number_diffs(
    pages: list[list[str]], boundaries: list[set[int]]
) -> set[int]:
    """Desplazamientos folio-impreso - número de página del PDF que se repiten."""
    seen: Counter[int] = Counter()
    for page_no, (lines, indexes) in enumerate(zip(pages, boundaries), start=1):
        for i in indexes:
            match = _PAGE_NUMBER.match(lines[i])
            if match:
                seen[int(match.group(1)) - page_no] += 1

    if not seen:
        return set()

    minimum = max(_FOLIO_MIN_COUNT, math.ceil(len(pages) * _FOLIO_RATIO))
    return {diff for diff, count in seen.items() if count >= minimum}


def _join_pages(page_texts: list[str]) -> tuple[str, int]:
    """Une páginas resolviendo palabras partidas justo en el salto de página."""
    if not page_texts:
        return "", 0

    joined = page_texts[0]
    extra_joins = 0

    for page in page_texts[1:]:
        if not page:
            continue
        if not joined:
            joined = page
            continue

        last = joined.rstrip()
        first = page.lstrip()

        if last and first and last[-1] in "-\u2010\u2011" and first[0].islower():
            joined = last[:-1] + first
            extra_joins += 1
        else:
            joined = last + "\n\n" + first

    return joined, extra_joins


def clean_ocr_pages(pages: list[str]) -> OcrCleanResult:
    """Limpia una lista de páginas OCR (en orden) y devuelve el texto final."""
    if not pages:
        return OcrCleanResult("")

    normalized = [[_normalize_line(line) for line in page.splitlines()] for page in pages]
    boundaries = [_boundary_indexes(lines) for lines in normalized]
    folio_diffs = _page_number_diffs(normalized, boundaries)

    header_counts: Counter[str] = Counter()
    for lines, indexes in zip(normalized, boundaries):
        for i in indexes:
            key = _header_candidate(lines[i])
            if key:
                header_counts[key] += 1

    header_min = max(_HEADER_MIN_COUNT, math.ceil(len(pages) * _HEADER_RATIO))
    repeated_headers = {key for key, count in header_counts.items() if count >= header_min}
    seen_headers: set[str] = set()

    page_texts: list[str] = []
    hyphen_joins = page_numbers = headers = noise = 0

    for page_no, (lines, indexes) in enumerate(zip(normalized, boundaries), start=1):
        kept: list[str] = []

        for i, line in enumerate(lines):
            if line:
                match = _PAGE_NUMBER.match(line)
                blank_before = i == 0 or not lines[i - 1]
                blank_after = i == len(lines) - 1 or not lines[i + 1]

                # Folio al borde de la página, o número aislado entre líneas en
                # blanco (portadillas, páginas con ilustraciones, etc.).
                if match and (
                    (i in indexes and (int(match.group(1)) - page_no) in folio_diffs)
                    or (blank_before and blank_after)
                ):
                    page_numbers += 1
                    continue

            if i in indexes and line:
                if _NOISE.match(line) and len(line) <= 5:
                    noise += 1
                    continue

                key = _header_candidate(line)
                if key in repeated_headers:
                    if key in seen_headers:
                        headers += 1
                        continue
                    seen_headers.add(key)

            kept.append(line)

        while kept and not kept[0]:
            kept.pop(0)
        while kept and not kept[-1]:
            kept.pop()

        page_texts.append("\n".join(kept))

    # Los guiones de final de línea se resuelven página a página y, después,
    # también en los saltos entre páginas.
    partial: list[str] = []
    for text in page_texts:
        cleaned, joins = _HYPHEN_BREAK.subn("", text)
        partial.append(cleaned)
        hyphen_joins += joins

    joined, cross_page_joins = _join_pages(partial)
    hyphen_joins += cross_page_joins

    text = joined.replace(_SOFT_HYPHEN, "").translate(_LIGATURES)
    text = _BLANK_LINES.sub("\n\n", text).strip()

    return OcrCleanResult(
        text=text,
        hyphen_joins=hyphen_joins,
        page_numbers_removed=page_numbers,
        headers_removed=headers,
        noise_lines_removed=noise,
    )


def clean_ocr_text(text: str) -> OcrCleanResult:
    """Limpia un texto OCR ya extraído (sin información de páginas)."""
    return clean_ocr_pages([text])
