"""Detección y análisis de pausas explícitas en texto narrativo.

Marcas soportadas:
    [pausa=1.5s]
    [silencio=2s]
    [pausa=1500ms]

Este módulo no genera audio. Solo parsea y resume bloques de texto y pausa.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


class PauseError(RuntimeError):
    pass


PAUSE_RE = re.compile(
    r"\[\s*(?P<name>pausa|silencio)\s*=\s*"
    r"(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>s|ms)?\s*\]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TextBlock:
    kind: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class PauseBlock:
    kind: str
    name: str
    seconds: float
    start: int
    end: int


Block = TextBlock | PauseBlock


def _merge_and_clean(blocks: list[Block]) -> list[Block]:
    """Merge bloques de texto adyacentes y descarta textos vacíos."""
    merged: list[Block] = []

    for b in blocks:
        if isinstance(b, TextBlock):
            if merged and isinstance(merged[-1], TextBlock):
                prev = merged[-1]
                merged[-1] = TextBlock(
                    kind="text",
                    text=prev.text + b.text,
                    start=prev.start,
                    end=b.end,
                )
            else:
                merged.append(b)
        else:
            merged.append(b)

    clean: list[Block] = []
    for b in merged:
        if isinstance(b, TextBlock):
            if b.text.strip():
                clean.append(b)
        else:
            clean.append(b)

    return clean


def parse_blocks(text: str, *, max_pause_s: float = 120.0) -> list[Block]:
    """Convierte texto con marcas en bloques alternos de texto/pausa."""
    blocks: list[Block] = []
    pos = 0

    for m in PAUSE_RE.finditer(text):
        if m.start() > pos:
            blocks.append(
                TextBlock(
                    kind="text",
                    text=text[pos:m.start()],
                    start=pos,
                    end=m.start(),
                )
            )

        raw_value = m.group("value").replace(",", ".")
        try:
            value = float(raw_value)
        except Exception as exc:
            raise PauseError(f"Valor de pausa inválido: {m.group(0)!r}") from exc

        unit = (m.group("unit") or "s").lower()
        seconds = value / 1000.0 if unit == "ms" else value

        if seconds < 0:
            raise PauseError(f"Pausa negativa no permitida: {m.group(0)!r}")

        if seconds > max_pause_s:
            raise PauseError(
                f"Pausa demasiado larga ({seconds:g}s). Máximo permitido: {max_pause_s:g}s. "
                f"Marca: {m.group(0)!r}"
            )

        name = m.group("name").lower()

        # Una pausa de 0 s se elimina como marca, pero no añade bloque de silencio.
        if seconds > 0:
            blocks.append(
                PauseBlock(
                    kind="pause",
                    name=name,
                    seconds=seconds,
                    start=m.start(),
                    end=m.end(),
                )
            )

        pos = m.end()

    if pos < len(text):
        blocks.append(
            TextBlock(
                kind="text",
                text=text[pos:],
                start=pos,
                end=len(text),
            )
        )

    return _merge_and_clean(blocks)


def has_explicit_pauses(text: str) -> bool:
    return bool(PAUSE_RE.search(text))


def strip_pause_markers(text: str) -> str:
    """Devuelve el texto sin marcas, útil para previews o normalización."""
    return PAUSE_RE.sub("", text)


def pause_count(blocks: list[Block]) -> int:
    return sum(1 for b in blocks if isinstance(b, PauseBlock))


def total_pause_seconds(blocks: list[Block]) -> float:
    return sum(float(b.seconds) for b in blocks if isinstance(b, PauseBlock))


def text_blocks(blocks: list[Block]) -> list[TextBlock]:
    return [b for b in blocks if isinstance(b, TextBlock)]


def summarize_blocks(blocks: list[Block]) -> dict:
    tb = text_blocks(blocks)
    return {
        "blocks": len(blocks),
        "text_blocks": len(tb),
        "pause_blocks": pause_count(blocks),
        "total_pause_s": total_pause_seconds(blocks),
        "useful_chars": sum(len(b.text.strip()) for b in tb),
    }