"""Troceado de texto en fragmentos aptos para el motor de voz, con soporte de pausas explícitas."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .pausetext import PauseBlock, parse_blocks

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_CLAUSE_END = re.compile(r"(?<=[,;:])\s+")

SEGMENT_TEXT = "text"
SEGMENT_PAUSE = "pause"


@dataclass(frozen=True)
class Chunk:
    text: str
    paragraph_end: bool  # True si el fragmento cierra un párrafo (pausa más larga)


@dataclass(frozen=True)
class Segment:
    """Segmento de narración: texto para TTS o pausa explícita."""

    kind: str
    text: str = ""
    paragraph_end: bool = False
    seconds: float = 0.0
    name: str = ""


def _pack(pieces: list[str], max_chars: int) -> list[str]:
    """Agrupa piezas consecutivas sin superar max_chars."""
    out: list[str] = []
    cur = ""
    for piece in pieces:
        if cur and len(cur) + 1 + len(piece) > max_chars:
            out.append(cur)
            cur = piece
        else:
            cur = f"{cur} {piece}".strip()
    if cur:
        out.append(cur)
    return out


def _split_long(sentence: str, max_chars: int) -> list[str]:
    """Parte una frase demasiado larga: primero por comas/puntos y comas, luego por palabras."""
    if len(sentence) <= max_chars:
        return [sentence]
    pieces: list[str] = []
    for clause in _CLAUSE_END.split(sentence):
        pieces.extend(_pack(clause.split(), max_chars) if len(clause) > max_chars else [clause])
    return _pack(pieces, max_chars)


def split_text(text: str, max_chars: int = 220) -> list[Chunk]:
    chunks: list[Chunk] = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        paragraph = " ".join(paragraph.split())
        if not paragraph:
            continue
        pieces: list[str] = []
        for sentence in _SENTENCE_END.split(paragraph):
            pieces.extend(_split_long(sentence, max_chars))
        packed = _pack(pieces, max_chars)
        chunks.extend(Chunk(t, False) for t in packed[:-1])
        chunks.append(Chunk(packed[-1], True))
    return chunks


def split_segments(text: str, max_chars: int = 220) -> list[Segment]:
    """Divide texto con pausas explícitas en segmentos de texto/pausa.

    Las marcas [pausa=...] y [silencio=...] no se pasan al TTS.
    Los bloques de texto se trocean igual que antes, preservando la caché
    cuando no hay pausas o cuando la pausa no altera el texto vecino.
    """
    segments: list[Segment] = []

    for block in parse_blocks(text):
        if isinstance(block, PauseBlock):
            segments.append(
                Segment(
                    kind=SEGMENT_PAUSE,
                    seconds=float(block.seconds),
                    name=block.name,
                )
            )
        else:
            for chunk in split_text(block.text, max_chars):
                segments.append(
                    Segment(
                        kind=SEGMENT_TEXT,
                        text=chunk.text,
                        paragraph_end=chunk.paragraph_end,
                    )
                )

    return segments