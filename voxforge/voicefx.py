"""Post-proceso de audio para VoxForge (Fase 4: Voice FX).

v1: presets de narración/podcast/radio/cine + normalize LUFS + batch + hardening.
v2 (4.2): presets creativos (sala, catedral, radio_vintage, susurro, eco) con ffmpeg.
v3 (Fase 3): presets profesionales para audiolibros (EBU R128, de-esser, noise gate).

Cadenas de procesamiento profesional:
- audiolibro_pro: Cadena completa para audiolibros comerciales
- audiolibro_ebu: Cumplimiento estricto EBU R128
- podcast_pro: Podcast profesional con compresión multibanda
- voz_limpia: Reducción de ruido + de-essing + normalización
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf

from voxforge.utils import AudioValidationError, validate_audio_file

import soundfile as sf


class FxError(RuntimeError):
    pass


@dataclass(frozen=True)
class Preset:
    name: str
    description: str
    filters: str


PRESETS: dict[str, Preset] = {
    # ---- v1: narración / masterización ----
    "neutro": Preset(
        "neutro",
        "Limpieza mínima: corta subsónicos y limita pico.",
        "highpass=f=50,"
        "alimiter=limit=0.89:attack=5:release=50",
    ),
    "narracion": Preset(
        "narracion",
        "Narración/audiolibro: voz clara, compresión suave y pico controlado.",
        "highpass=f=80,"
        "lowpass=f=15000,"
        "equalizer=f=2500:t=q:w=1:g=1.5,"
        "acompressor=threshold=-18dB:ratio=2.5:attack=15:release=250:makeup=1.5,"
        "alimiter=limit=0.89:attack=5:release=50",
    ),
    "podcast": Preset(
        "podcast",
        "Podcast: cuerpo reducido, presencia media y control dinámico.",
        "highpass=f=90,"
        "lowpass=f=14000,"
        "equalizer=f=100:t=q:w=1:g=-1,"
        "equalizer=f=3000:t=q:w=1:g=2,"
        "equalizer=f=8000:t=q:w=1:g=1,"
        "acompressor=threshold=-20dB:ratio=3:attack=10:release=200:makeup=2,"
        "alimiter=limit=0.90:attack=5:release=50",
    ),
    "radio": Preset(
        "radio",
        "Radio: compresión más marcada y brillo controlado.",
        "highpass=f=100,"
        "lowpass=f=12000,"
        "equalizer=f=200:t=q:w=1:g=-2,"
        "equalizer=f=3000:t=q:w=1:g=3,"
        "equalizer=f=8000:t=q:w=1:g=2,"
        "acompressor=threshold=-15dB:ratio=4:attack=5:release=150:makeup=3,"
        "alimiter=limit=0.92:attack=3:release=40",
    ),
    "cine": Preset(
        "cine",
        "Cine/atmósfera: rango algo más amplio y limite conservador.",
        "highpass=f=60,"
        "lowpass=f=18000,"
        "equalizer=f=60:t=q:w=1:g=1,"
        "equalizer=f=200:t=q:w=1:g=-1,"
        "equalizer=f=3000:t=q:w=1:g=1,"
        "equalizer=f=10000:t=q:w=1:g=1,"
        "acompressor=threshold=-20dB:ratio=2:attack=20:release=300:makeup=1,"
        "alimiter=limit=0.85:attack=5:release=80",
    ),
    # ---- v2 (4.2): creativos / atmósfera ----
    "sala": Preset(
        "sala",
        "Reverb corta de habitación: voz con cuerpo, locución íntima.",
        "highpass=f=80,"
        "lowpass=f=14000,"
        "aecho=0.8:0.85:30|45:0.22|0.18,"
        "acompressor=threshold=-18dB:ratio=2:attack=15:release=250:makeup=1,"
        "alimiter=limit=0.89:attack=5:release=50",
    ),
    "catedral": Preset(
        "catedral",
        "Reverb amplia y oscura: atmósfera ritual, intros, producción audiovisual.",
        "highpass=f=60,"
        "lowpass=f=9000,"
        "equalizer=f=200:t=q:w=1:g=2,"
        "aecho=0.8:0.8:60|120|180|260:0.30|0.25|0.20|0.15,"
        "acompressor=threshold=-20dB:ratio=2:attack=20:release=300:makeup=1,"
        "alimiter=limit=0.85:attack=5:release=80",
    ),
    "radio_vintage": Preset(
        "radio_vintage",
        "Banda estrecha + compresión + tremolo leve: efecto radio antigua.",
        "highpass=f=300,"
        "lowpass=f=3400,"
        "equalizer=f=1000:t=q:w=1:g=3,"
        "acompressor=threshold=-12dB:ratio=6:attack=5:release=120:makeup=4,"
        "tremolo=f=6:d=0.15,"
        "alimiter=limit=0.92:attack=3:release=40",
    ),
    "susurro": Preset(
        "susurro",
        "Compresión fuerte + highpass + reverb mínima: voz cercana y tensa.",
        "highpass=f=120,"
        "lowpass=f=12000,"
        "equalizer=f=4000:t=q:w=1:g=2,"
        "acompressor=threshold=-24dB:ratio=5:attack=8:release=180:makeup=3,"
        "aecho=0.8:0.8:25:0.12,"
        "alimiter=limit=0.88:attack=4:release=50",
    ),
    "eco": Preset(
        "eco",
        "Delay simple único: transiciones, énfasis, cierre de frase.",
        "highpass=f=80,"
        "lowpass=f=14000,"
        "aecho=0.8:0.85:350:0.35,"
        "acompressor=threshold=-18dB:ratio=2:attack=15:release=250:makeup=1,"
        "alimiter=limit=0.89:attack=5:release=50",
    ),
    # ---- v3: Profesionales / Audiolibros (EBU R128) ----
    "audiolibro_pro": Preset(
        "audiolibro_pro",
        "Audiolibro profesional: cadena completa EBU R128 + de-essing + noise gate + compresión.",
        # Filtro de banda: 80Hz-16000Hz (estándar para voz humana)
        "highpass=f=80:width_type=h:width=0.5,"
        "lowpass=f=16000:width_type=h:width=0.5,"
        # De-esser: reducir sibilantes en 3-8 kHz
        "equalizer=f=4000:t=q:w=0.8:g=-3,"
        "equalizer=f=6000:t=q:w=0.8:g=-2,"
        # Noise gate: eliminar silencio/ruido de fondo
        # level_in=0.02 (≈-34dB), attack=0.01 (10ms mínimo), release=0.1 (100ms)
        "agate=level_in=0.02:attack=0.01:release=0.1,"
        # EQ: mejorar claridad
        "equalizer=f=150:t=q:w=1:g=1.5,"
        "equalizer=f=2500:t=q:w=1:g=1.2,"
        "equalizer=f=10000:t=q:w=1:g=0.8,"
        # Compresión suave multibanda
        "compand=attacks=0.01:decays=0.1:points=-60/-60|-30/-20|-10/-10|0/-8:gain=4,"
    ),
    "audiolibro_ebu": Preset(
        "audiolibro_ebu",
        "EBU R128 estricto: normalización de loudness sin distorsión, ideal para audiolibros.",
        "highpass=f=50,"
        "lowpass=f=18000,"
        # Compresión muy suave para mantener rango dinámico
        "acompressor=threshold=-24dB:ratio=1.5:attack=30:release=500:makeup=1,"
    ),
    "podcast_pro": Preset(
        "podcast_pro",
        "Podcast profesional: compresión multibanda + de-essing + noise gate.",
        "highpass=f=90,"
        "lowpass=f=15000,"
        # De-esser
        "equalizer=f=3500:t=q:w=0.7:g=-2.5,"
        "equalizer=f=5000:t=q:w=0.7:g=-1.5,"
        # Noise gate (level_in=0.025 ≈ -32dB)
        "agate=level_in=0.025:attack=0.01:release=0.08,"
        # EQ para cuerpo
        "equalizer=f=120:t=q:w=1:g=1.8,"
        "equalizer=f=3000:t=q:w=1:g=2,"
        "equalizer=f=10000:t=q:w=1:g=1,"
        # Compresión multibanda
        "compand=attacks=0.01:decays=0.1:points=-50/-50|-25/-15|-10/-8|0/-6:gain=3,"
    ),
    "voz_limpia": Preset(
        "voz_limpia",
        "Voz limpia: reducción de ruido agresiva + de-essing + normalización suave.",
        "highpass=f=100,"
        "lowpass=f=14000,"
        # De-esser agresivo
        "equalizer=f=3000:t=q:w=1:g=-3,"
        "equalizer=f=5000:t=q:w=1:g=-2,"
        "equalizer=f=7000:t=q:w=0.8:g=-1,"
        # Noise gate agresivo (level_in=0.016 ≈ -36dB, mínimo)
        "agate=level_in=0.016:attack=0.01:release=0.06,"
        # Compresión suave
        "acompressor=threshold=-20dB:ratio=2:attack=10:release=200:makeup=1,"
    ),
    "master_pro": Preset(
        "master_pro",
        "Masterización profesional: cadena completa para distribución.",
        "highpass=f=40:width_type=h:width=0.3,"
        "lowpass=f=18000:width_type=h:width=0.3,"
        # De-esser
        "equalizer=f=4000:t=q:w=0.5:g=-2,"
        # Noise gate suave (level_in=0.016 ≈ -36dB)
        "agate=level_in=0.016:attack=0.01:release=0.12,"
        # EQ de masterización
        "equalizer=f=60:t=q:w=1:g=1,"
        "equalizer=f=250:t=q:w=1:g=0.8,"
        "equalizer=f=5000:t=q:w=1:g=1,"
        "equalizer=f=12000:t=q:w=1:g=0.5,"
        # Compresión multibanda
        "compand=attacks=0.01:decays=0.1:points=-60/-60|-30/-18|-10/-10|0/-8:gain=2,"
    ),
}

# ---- hardening: margen automático de true peak para formatos con pérdida ----
LOSSY_AUDIO_EXTS = {".mp3", ".ogg", ".oga", ".m4a", ".aac"}
LOSSY_TRUE_PEAK_FLOOR = -2.0

AUDIO_EXTS = {".wav", ".flac", ".mp3", ".ogg", ".oga", ".m4a", ".aac"}


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def _num(value: object) -> float | None:
    try:
        x = float(value)  # type: ignore[arg-type]
    except Exception:
        return None
    return x if math.isfinite(x) else None


def _fmt(value: float | None, unit: str = "") -> str:
    if value is None:
        return "n/d"
    return f"{value:.2f}{unit}"


def _is_lossy_audio(ext: str) -> bool:
    return ext.lower() in LOSSY_AUDIO_EXTS


def analyze_audio(path: Path) -> dict:
    """Analiza LUFS integrado, pico verdadero y rango dinámico usando ffmpeg/loudnorm."""
    if not path.is_file():
        raise FxError(f"No existe el archivo: {path}")

    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-map", "0:a:0",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-",
    ]

    result = _run(cmd)
    if result.returncode != 0:
        raise FxError(f"ffmpeg no pudo analizar el audio:\n{result.stderr}")

    stderr = result.stderr or ""
    data: dict | None = None

    for match in reversed(list(re.finditer(r"\{[\s\S]*?\}", stderr))):
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                data = parsed
                break
        except Exception:
            continue

    if data is None:
        raise FxError("No se pudo interpretar la salida de loudnorm.")

    return data


def format_analysis(data: dict) -> str:
    lines = []
    mapping = [
        ("input_i", "LUFS integrado"),
        ("input_tp", "Pico verdadero (dBTP)"),
        ("input_lra", "Rango dinámico (LU)"),
        ("input_thresh", "Umbral (dB)"),
        ("target_offset", "Offset objetivo (dB)"),
    ]
    for key, label in mapping:
        if key in data:
            lines.append(f"  {label:<28} {_fmt(_num(data[key]))}")
    if not lines:
        return "  Sin métricas disponibles."
    return "\n".join(lines)


def _codec_args(dest: Path) -> list[str]:
    suffix = dest.suffix.lower()
    if suffix == ".wav":
        return ["-c:a", "pcm_s24le"]
    if suffix == ".flac":
        return ["-c:a", "flac"]
    if suffix == ".mp3":
        return ["-c:a", "libmp3lame", "-q:a", "2"]
    if suffix in (".ogg", ".oga"):
        return ["-c:a", "libvorbis", "-q:a", "5"]
    return []


def apply_fx(
    src: Path,
    dest: Path,
    preset_name: str,
    *,
    gain_db: float = 0.0,
    force: bool = False,
    target_lufs: float | None = None,
    true_peak: float = -1.5,
    lra: float = 11.0,
) -> Path:
    """Aplica un preset de post-proceso a un archivo de audio.

    Si se indica target_lufs, tras el preset se normaliza con loudnorm en dos
    pasadas, usando un WAV intermedio para evitar doble compresión con pérdida.
    Cuando la salida es formato con pérdida y se normaliza, se aplica el mismo
    margen de true peak que en batch_process.
    """
    if preset_name not in PRESETS:
        raise FxError(
            f"Preset desconocido: {preset_name}. "
            f"Disponibles: {', '.join(sorted(PRESETS))}"
        )
    if not src.is_file():
        raise FxError(f"No existe el archivo: {src}")
    if dest.exists() and not force:
        raise FxError(
            f"Ya existe {dest}. Usa --force para sobrescribirlo o elige otro --out."
        )

    preset = PRESETS[preset_name]
    filters = preset.filters
    if abs(gain_db) > 1e-9:
        filters = f"volume={gain_db:g}dB,{filters}"

    dest.parent.mkdir(parents=True, exist_ok=True)

    if target_lufs is None:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
            "-map", "0:a:0", "-filter:a", filters,
        ]
        cmd.extend(_codec_args(dest))
        cmd.append(str(dest))
        result = _run(cmd)
        if result.returncode != 0:
            raise FxError(f"ffmpeg no pudo procesar el audio:\n{result.stderr}")
        # Validar integridad del archivo de salida
        try:
            validate_audio_file(dest, require_non_silent=False)
        except AudioValidationError as exc:
            dest.unlink(missing_ok=True)
            raise FxError(f"ffmpeg produjo archivo de audio corrupto: {dest} ({exc})")
        return dest

    # Ruta con normalización: preset -> WAV temporal -> loudnorm -> dest.
    temp = dest.with_name(dest.stem + ".fx.wav")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-map", "0:a:0", "-filter:a", filters, "-c:a", "pcm_s24le", str(temp),
    ]
    result = _run(cmd)
    if result.returncode != 0:
        temp.unlink(missing_ok=True)
        raise FxError(f"ffmpeg no pudo aplicar el preset:\n{result.stderr}")
    # Validar que el archivo temporal intermedio es legible antes de normalizar
    try:
        validate_audio_file(temp, require_non_silent=False)
    except AudioValidationError as exc:
        temp.unlink(missing_ok=True)
        raise FxError(f"ffmpeg produjo audio intermedio corrupto: {temp} ({exc})")

    effective_true_peak = true_peak
    if (
        _is_lossy_audio(dest.suffix)
        and effective_true_peak > LOSSY_TRUE_PEAK_FLOOR
    ):
        effective_true_peak = LOSSY_TRUE_PEAK_FLOOR

    try:
        normalize_lufs(
            temp, dest,
            target_lufs=target_lufs,
            true_peak=effective_true_peak,
            lra=lra,
            force=force,
        )
    finally:
        temp.unlink(missing_ok=True)

    return dest


def _parse_loudnorm_json(stderr: str) -> dict:
    for match in reversed(list(re.finditer(r"\{[\s\S]*?\}", stderr))):
        try:
            parsed = json.loads(match.group(0))
        except Exception:
            continue
        if isinstance(parsed, dict) and "input_i" in parsed:
            return parsed
    raise FxError("No se pudo interpretar la salida JSON de loudnorm.")


def _loudnorm_measure(path: Path, target_lufs: float, true_peak: float, lra: float) -> dict:
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-map", "0:a:0",
        "-af", f"loudnorm=I={target_lufs:g}:TP={true_peak:g}:LRA={lra:g}:print_format=json",
        "-f", "null", "-",
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise FxError(f"ffmpeg no pudo medir loudnorm:\n{result.stderr}")
    return _parse_loudnorm_json(result.stderr or "")


def _float_or_raise(data: dict, key: str, default: float | None = None) -> float:
    if key not in data:
        if default is not None:
            return default
        raise FxError(f"loudnorm no devolvió el campo obligatorio: {key}")
    try:
        value = float(data[key])
    except Exception as exc:
        raise FxError(f"Campo inválido en loudnorm JSON: {key}={data[key]!r}") from exc
    if not math.isfinite(value):
        raise FxError(f"Campo no finito en loudnorm JSON: {key}={data[key]!r}")
    return value


def normalize_lufs(
    src: Path,
    dest: Path,
    *,
    target_lufs: float = -16.0,
    true_peak: float = -1.5,
    lra: float = 11.0,
    force: bool = False,
) -> Path:
    """Normaliza loudness con loudnorm en dos pasadas."""
    if not src.is_file():
        raise FxError(f"No existe el archivo: {src}")
    if dest.exists() and not force:
        raise FxError(
            f"Ya existe {dest}. Usa --force para sobrescribirlo o elige otro --out."
        )

    measured = _loudnorm_measure(src, target_lufs, true_peak, lra)
    measured_i = _float_or_raise(measured, "input_i")
    measured_tp = _float_or_raise(measured, "input_tp")
    measured_lra = _float_or_raise(measured, "input_lra")
    measured_thresh = _float_or_raise(measured, "input_thresh")
    offset = _float_or_raise(measured, "target_offset", default=0.0)

    dest.parent.mkdir(parents=True, exist_ok=True)

    def _run_normalization(linear: bool) -> subprocess.CompletedProcess[str]:
        filter_spec = (
            f"loudnorm=I={target_lufs:g}:TP={true_peak:g}:LRA={lra:g}:"
            f"measured_I={measured_i:g}:measured_TP={measured_tp:g}:"
            f"measured_LRA={measured_lra:g}:measured_thresh={measured_thresh:g}:"
            f"offset={offset:g}:linear={'true' if linear else 'false'}:"
            "print_format=summary"
        )
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
            "-map", "0:a:0", "-af", filter_spec,
        ]
        cmd.extend(_codec_args(dest))
        cmd.append(str(dest))
        return _run(cmd)

    result = _run_normalization(True)
    if result.returncode != 0:
        result = _run_normalization(False)
        if result.returncode != 0:
            raise FxError(f"ffmpeg no pudo normalizar el audio:\n{result.stderr}")
    # Validar integridad del archivo normalizado antes de devolverlo
    try:
        validate_audio_file(dest, require_non_silent=False)
    except AudioValidationError as exc:
        dest.unlink(missing_ok=True)
        raise FxError(f"ffmpeg produjo audio normalizado corrupto: {dest} ({exc})")

    return dest


# --------------------------------------------------------------------------- #
# Batch                                                                        #
# --------------------------------------------------------------------------- #

def _iter_audio_files(src_dir: Path, recursive: bool = False):
    it = src_dir.rglob("*") if recursive else src_dir.glob("*")
    for path in sorted(it):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTS:
            yield path


def _convert_audio(src: Path, dest: Path, *, force: bool = False) -> Path:
    if not src.is_file():
        raise FxError(f"No existe el archivo: {src}")
    if dest.exists() and not force:
        raise FxError(
            f"Ya existe {dest}. Usa --force para sobrescribirlo o elige otro --out."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-map", "0:a:0"]
    cmd.extend(_codec_args(dest))
    cmd.append(str(dest))
    result = _run(cmd)
    if result.returncode != 0:
        raise FxError(f"ffmpeg no pudo convertir el audio:\n{result.stderr}")
    return dest


def batch_process(
    src_dir: Path,
    out_dir: Path,
    *,
    preset: str | None = None,
    target_lufs: float | None = None,
    true_peak: float = -1.5,
    lra: float = 11.0,
    out_format: str | None = None,
    gain_db: float = 0.0,
    force: bool = False,
    recursive: bool = False,
    log=print,
) -> dict:
    """Procesa por lotes un directorio de audios.

    Hardening: cuando la salida es formato con pérdida y se normaliza LUFS,
    se reduce automáticamente el true peak objetivo a -2.0 dBTP como mínimo.
    """
    if not src_dir.is_dir():
        raise FxError(f"No existe el directorio: {src_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_res = out_dir.resolve()

    files = [
        path
        for path in _iter_audio_files(src_dir, recursive=recursive)
        if not path.resolve().is_relative_to(out_res)
    ]
    if not files:
        return {"processed": 0, "failed": [], "output_dir": str(out_dir)}

    out_ext = "." + out_format.lstrip(".").lower() if out_format else None

    processed = 0
    failed: list[dict] = []
    warned_lossy_margin = False

    for src in files:
        dest_ext = out_ext or src.suffix.lower()
        dest = out_dir / f"{src.stem}{dest_ext}"

        if dest == src.resolve():
            failed.append({"file": str(src), "error": "la salida coincide con la entrada; usa --out-dir distinto"})
            log(f"ERROR: {src.name}: la salida coincide con la entrada; usa --out-dir distinto")
            continue

        effective_true_peak = true_peak
        if (
            target_lufs is not None
            and _is_lossy_audio(dest_ext)
            and effective_true_peak > LOSSY_TRUE_PEAK_FLOOR
        ):
            effective_true_peak = LOSSY_TRUE_PEAK_FLOOR
            if not warned_lossy_margin:
                log(
                    f"Aviso: formato de salida con pérdida ({dest_ext}); "
                    f"margen de true peak reducido de {true_peak:g} a "
                    f"{effective_true_peak:g} dBTP para evitar overshoot tras codificación."
                )
                warned_lossy_margin = True

        try:
            if preset and target_lufs is not None:
                temp = dest.with_name(dest.stem + ".fx.wav")
                apply_fx(src, temp, preset, gain_db=gain_db, force=True)
                normalize_lufs(
                    temp, dest,
                    target_lufs=target_lufs, true_peak=effective_true_peak, lra=lra, force=force,
                )
                temp.unlink(missing_ok=True)
            elif preset:
                apply_fx(src, dest, preset, gain_db=gain_db, force=force)
            elif target_lufs is not None:
                normalize_lufs(
                    src, dest,
                    target_lufs=target_lufs, true_peak=effective_true_peak, lra=lra, force=force,
                )
            else:
                _convert_audio(src, dest, force=force)

            processed += 1
            log(f"OK: {src.name} -> {dest}")
        except Exception as exc:
            failed.append({"file": str(src), "error": str(exc)})
            log(f"ERROR: {src.name}: {exc}")

    return {"processed": processed, "failed": failed, "output_dir": str(out_dir)}


# --------------------------------------------------------------------------- #
# Funciones específicas de procesamiento (para uso individual)             #
# --------------------------------------------------------------------------- #

def deess_audio(
    src: Path,
    dest: Path,
    *,
    frequency: float = 4000.0,
    bandwidth: float = 1000.0,
    gain: float = -2.0,
    force: bool = False,
) -> Path:
    """Aplica de-essing a un archivo de audio para reducir sibilantes.
    
    Las sibilantes (s, sh, ch) suelen estar en el rango de 4-8 kHz.
    Esta función aplica un filtro de EQ para reducir ese rango.
    
    Args:
        src: Archivo de entrada.
        dest: Archivo de salida.
        frequency: Frecuencia central para el de-esser (Hz).
        bandwidth: Ancho de banda (Hz).
        gain: Ganancia negativa para reducir (dB).
        force: Sobrescribir si existe.
    
    Returns:
        Path del archivo de salida.
    """
    if not src.is_file():
        raise FxError(f"No existe el archivo: {src}")
    if dest.exists() and not force:
        raise FxError(
            f"Ya existe {dest}. Usa --force para sobrescribirlo o elige otro --out."
        )
    
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    # Aplicar EQ para reducir sibilantes
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-map", "0:a:0",
        "-filter:a",
        f"equalizer=f={frequency}:t=q:w={bandwidth/1000}:g={gain}",
        "-c:a", "pcm_s24le",
        str(dest),
    ]
    
    result = _run(cmd)
    if result.returncode != 0:
        raise FxError(f"ffmpeg falló al aplicar de-esser:\n{result.stderr}")
    
    return dest


def noise_gate(
    src: Path,
    dest: Path,
    *,
    level_in: float = 0.02,   # Nivel de entrada (0.02 ≈ -34dB)
    attack: float = 0.01,     # Tiempo de ataque en segundos (10ms mínimo)
    release: float = 0.1,     # Tiempo de release en segundos (100ms)
    force: bool = False,
) -> Path:
    """Aplica noise gate a un archivo de audio para eliminar silencio/ruido de fondo.
    
    El filtro agate de FFmpeg usa level_in (nivel lineal, no dB).
    En FFmpeg 8.x, el rango para level_in es [0.015625, 64].
    El rango para attack y release es [0.01, 9000] (en segundos).
    
    level_in=0.016 ≈ -36dB (mínimo), level_in=0.02 ≈ -34dB, level_in=0.03 ≈ -30dB.
    
    Args:
        src: Archivo de entrada.
        dest: Archivo de salida.
        level_in: Nivel de entrada en escala lineal (0.015625-64).
        attack: Tiempo de ataque en segundos (0.01-9000).
        release: Tiempo de release en segundos (0.01-9000).
        force: Sobrescribir si existe.
    
    Returns:
        Path del archivo de salida.
    """
    if not src.is_file():
        raise FxError(f"No existe el archivo: {src}")
    if dest.exists() and not force:
        raise FxError(
            f"Ya existe {dest}. Usa --force para sobrescribirlo o elige otro --out."
        )
    
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    # Aplicar noise gate
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-map", "0:a:0",
        "-filter:a",
        f"agate=level_in={level_in}:attack={attack}:release={release}",
        "-c:a", "pcm_s24le",
        str(dest),
    ]
    
    result = _run(cmd)
    if result.returncode != 0:
        raise FxError(f"ffmpeg falló al aplicar noise gate:\n{result.stderr}")
    
    return dest


def multiband_compress(
    src: Path,
    dest: Path,
    *,
    points: str = "-60/-60|-30/-20|-10/-10|0/-8",
    gain: float = 4.0,
    attacks: float = 0.01,
    decays: float = 0.1,
    force: bool = False,
) -> Path:
    """Aplica compresión multibanda usando el filtro compand de FFmpeg.
    
    Args:
        src: Archivo de entrada.
        dest: Archivo de salida.
        points: Puntos de compresión en formato "input/output|input/output|..."
        gain: Ganancia de salida (dB).
        attacks: Tiempo de ataque para todas las bandas (segundos).
        decays: Tiempo de release para todas las bandas (segundos).
        force: Sobrescribir si existe.
    
    Returns:
        Path del archivo de salida.
    """
    if not src.is_file():
        raise FxError(f"No existe el archivo: {src}")
    if dest.exists() and not force:
        raise FxError(
            f"Ya existe {dest}. Usa --force para sobrescribirlo o elige otro --out."
        )
    
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    # Aplicar compresión multibanda
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-map", "0:a:0",
        "-filter:a",
        f"compand=attacks={attacks}:decays={decays}:points={points}:gain={gain}",
        "-c:a", "pcm_s24le",
        str(dest),
    ]
    
    result = _run(cmd)
    if result.returncode != 0:
        raise FxError(f"ffmpeg falló al aplicar compresión multibanda:\n{result.stderr}")
    
    return dest


def ensure_ebu_r128(
    src: Path,
    dest: Path,
    *,
    target_lufs: float = -16.0,
    true_peak: float = -1.5,
    lra: float = 11.0,
    force: bool = False,
) -> Path:
    """Aplica normalización EBU R128 a un archivo de audio.
    
    Esto es el estándar para audiolibros y broadcasting en Europa.
    
    Args:
        src: Archivo de entrada.
        dest: Archivo de salida.
        target_lufs: Nivel de loudness integrado objetivo (dB LUFS).
        true_peak: Pico verdadero máximo permitido (dB TP).
        lra: Rango dinámico objetivo (LU).
        force: Sobrescribir si existe.
    
    Returns:
        Path del archivo de salida.
    """
    # Esto es básicamente un wrapper de normalize_lufs
    return normalize_lufs(
        src, dest,
        target_lufs=target_lufs,
        true_peak=true_peak,
        lra=lra,
        force=force
    )


# --------------------------------------------------------------------------- #
# Preajustes rápidos para combinaciones comunes                              #
# --------------------------------------------------------------------------- #

def apply_professional_chain(
    src: Path,
    dest: Path,
    *,
    preset: str = "audiolibro_pro",
    target_lufs: float | None = -16.0,
    true_peak: float = -1.5,
    lra: float = 11.0,
    gain_db: float = 0.0,
    force: bool = False,
    log=print,
) -> Path:
    """Aplica una cadena profesional completa: preset + normalización EBU R128.
    
    Este es el método recomendado para producción de audiolibros.
    
    Args:
        src: Archivo de entrada.
        dest: Archivo de salida.
        preset: Nombre del preset a aplicar.
        target_lufs: Nivel LUFS objetivo (None para no normalizar).
        true_peak: Pico verdadero objetivo.
        lra: Rango dinámico objetivo.
        gain_db: Ganancia adicional en dB.
        force: Sobrescribir si existe.
        log: Función de logging.
    
    Returns:
        Path del archivo de salida.
    """
    if preset not in PRESETS:
        raise FxError(f"Preset desconocido: {preset}")
    
    # Si se pide normalización EBU R128
    if target_lufs is not None:
        # Aplicar preset a un archivo temporal
        temp = dest.with_name(dest.stem + ".pre_fx.wav")
        try:
            apply_fx(src, temp, preset, gain_db=gain_db, force=True)
            # Luego normalizar
            result = normalize_lufs(
                temp, dest,
                target_lufs=target_lufs,
                true_peak=true_peak,
                lra=lra,
                force=force
            )
            return result
        finally:
            temp.unlink(missing_ok=True)
    else:
        # Solo aplicar preset
        return apply_fx(src, dest, preset, gain_db=gain_db, force=force)