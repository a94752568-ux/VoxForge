"""Grabación desde el micrófono con ffmpeg (entrada PulseAudio/PipeWire)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

RECORD_RATE = 48000


class RecordingError(RuntimeError):
    pass


def input_args(source: str = "default") -> list[str]:
    """Argumentos de entrada de ffmpeg para el micrófono."""
    return ["-f", "pulse", "-i", source]


def _base(in_args: list[str], out_path: Path) -> list[str]:
    return ["ffmpeg", "-y", "-loglevel", "error", *in_args, "-ac", "1", "-ar", str(RECORD_RATE), str(out_path)]


def record_fixed(in_args: list[str], out_path: Path, seconds: float) -> None:
    """Graba una duración fija (se usa para medir el ruido de la sala)."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *in_args, "-t", str(seconds),
           "-ac", "1", "-ar", str(RECORD_RATE), str(out_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=seconds + 30)
    except FileNotFoundError as exc:
        raise RecordingError("No se encontró ffmpeg.") from exc
    if result.returncode != 0:
        raise RecordingError(result.stderr.strip() or "ffmpeg falló al grabar.")


def record_until(in_args: list[str], out_path: Path, wait: Callable[[], None]) -> None:
    """Graba hasta que `wait()` termine (p. ej. hasta que se pulse Enter) y cierra el archivo bien."""
    try:
        proc = subprocess.Popen(_base(in_args, out_path), stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise RecordingError("No se encontró ffmpeg.") from exc
    try:
        wait()
    finally:
        try:
            _, err = proc.communicate(input=b"q", timeout=15)  # 'q' = fin ordenado de ffmpeg
        except subprocess.TimeoutExpired:
            proc.kill()
            _, err = proc.communicate()
    if not out_path.exists() or out_path.stat().st_size < 1000:
        raise RecordingError((err or b"").decode(errors="replace").strip() or "No se grabó audio.")
