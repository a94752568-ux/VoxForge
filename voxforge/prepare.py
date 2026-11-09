"""Preparación de muestras de voz: filtro de graves, reducción de ruido, recorte y normalización.

Usa los filtros de ffmpeg (highpass y afftdn): sin dependencias nuevas. No modifica el original.
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from .audioqa import FRAME_S, _frame_db

SAMPLE_RATE = 24000


class PrepareError(RuntimeError):
    pass


@dataclass
class PrepareResult:
    before_s: float
    after_s: float
    noise_db: float       # ruido de fondo medido en la muestra original (ya convertida)
    gain_db: float        # ganancia aplicada en la normalización


def _ffmpeg(src: Path, dest: Path, audio_filter: str | None) -> None:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    if audio_filter:
        cmd += ["-af", audio_filter]
    cmd += ["-ac", "1", "-ar", str(SAMPLE_RATE), str(dest)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise PrepareError("No se encontró ffmpeg.") from exc
    if result.returncode != 0:
        raise PrepareError(result.stderr.strip() or "ffmpeg falló.")


def trim_and_compact(audio: np.ndarray, sr: int, margin_s: float = 0.25, max_pause_s: float = 1.0) -> np.ndarray:
    """Quita el silencio de los extremos (dejando un margen) y acorta las pausas largas internas."""
    size = max(int(sr * FRAME_S), 1)
    n = len(audio) // size
    if n == 0:
        return audio
    frames = audio[: n * size].reshape(n, size)
    db = _frame_db(audio[: n * size], sr)
    active = db > np.percentile(db, 10) + 10
    if not active.any():
        return audio
    margin = int(round(margin_s / FRAME_S))
    first = max(int(np.argmax(active)) - margin, 0)
    last = min(n - 1 - int(np.argmax(active[::-1])) + margin, n - 1)
    keep = np.zeros(n, dtype=bool)
    keep[first:last + 1] = True
    limit = int(round(max_pause_s / FRAME_S))
    i = first
    while i <= last:
        if active[i]:
            i += 1
            continue
        j = i
        while j <= last and not active[j]:
            j += 1
        if j - i > limit:
            keep[i + limit:j] = False  # se conserva el principio de la pausa
        i = j
    return frames[keep].reshape(-1)


def normalize_peak(audio: np.ndarray, target_db: float = -3.0, max_gain_db: float = 24.0) -> tuple[np.ndarray, float]:
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak < 1e-4:
        return audio, 0.0
    gain_db = min(target_db - 20 * np.log10(peak), max_gain_db)
    return (audio * 10 ** (gain_db / 20)).astype(np.float32), float(gain_db)


def prepare(src: Path, dest: Path, nr: float = 12.0, margin_s: float = 0.25,
            max_pause_s: float = 1.0, target_peak_db: float = -3.0) -> PrepareResult:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "base.wav"
        _ffmpeg(src, base, "highpass=f=70")  # convierte a mono 24 kHz y quita retumbos graves
        audio, sr = sf.read(base, dtype="float32")
        before_s = len(audio) / sr
        noise_db = float(np.percentile(_frame_db(audio, sr), 10))
        if nr > 0:
            den = Path(tmp) / "den.wav"
            nf = int(round(max(-80.0, min(-20.0, noise_db))))  # nivel de ruido que debe eliminar
            _ffmpeg(base, den, f"afftdn=nr={nr}:nf={nf}:tn=0")
            audio, sr = sf.read(den, dtype="float32")
    audio = trim_and_compact(audio, sr, margin_s, max_pause_s)
    audio, gain_db = normalize_peak(audio, target_peak_db)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(dest, audio, sr, subtype="PCM_16")
    return PrepareResult(before_s, len(audio) / sr, noise_db, gain_db)
