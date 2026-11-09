"""Comparación de voces: ¿cuánto se parece una grabación (o el clon) a una referencia?

Usa el codificador de hablante del propio motor (mismos pesos que ya están descargados).
Es una medida objetiva pero relativa: sirve para comparar A contra B, no como nota absoluta.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

Embedder = Callable[[np.ndarray, int], np.ndarray]  # (audio mono float32, sr) -> vector


@dataclass
class SimilarityResult:
    mean: float
    minimum: float
    windows: int


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a, b = np.asarray(a, dtype=np.float64).ravel(), np.asarray(b, dtype=np.float64).ravel()
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def window_slices(n: int, sr: int, window_s: float = 8.0, min_s: float = 3.0) -> list[slice]:
    """Ventanas consecutivas de window_s; la última se descarta si dura menos de min_s (salvo que sea la única)."""
    size = int(window_s * sr)
    slices = [slice(i, min(i + size, n)) for i in range(0, n, size)]
    kept = [s for s in slices if (s.stop - s.start) >= min_s * sr]
    return kept or slices[:1]


def compare(embed: Embedder, ref_embedding: np.ndarray, audio: np.ndarray, sr: int,
            window_s: float = 8.0) -> SimilarityResult:
    """Similitud media y mínima entre las ventanas de `audio` y la referencia."""
    scores = []
    for sl in window_slices(len(audio), sr, window_s):
        chunk = audio[sl]
        if float(np.sqrt(np.mean(chunk ** 2))) < 1e-4:  # ventana muda: no aporta información
            continue
        scores.append(cosine(embed(chunk, sr), ref_embedding))
    if not scores:
        return SimilarityResult(0.0, 0.0, 0)
    return SimilarityResult(float(np.mean(scores)), float(np.min(scores)), len(scores))
