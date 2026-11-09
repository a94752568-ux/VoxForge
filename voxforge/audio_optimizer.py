"""Optimización profesional de audio para VoxForge.

Aplica post-procesamiento a cada fragmento sintetizado para reducir
anomalías en el audio final: clicks en uniones, saltos de volumen,
clipping, DC offset, silencio anómalo en bordes, etc.

Todas las funciones operan sobre numpy arrays float32 y son puras
(sin efectos de lado), lo que las hace fáciles de testear y reutilizar.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Configuración de umbrales
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Umbral de detección de clipping (muestras >= este valor se consideran clip)
CLIP_THRESHOLD: float = 0.98

# Umbral de silencio para trimming de bordes (rms relativo al pico del fragmento)
SILENCE_RMS_RATIO: float = 0.005  # -46 dBFS relativo

# Duración mínima de fade para eliminar clicks (segundos)
FADE_MS: float = 5.0

# Ganancia objetivo RMS para normalización entre fragmentos (0.0-1.0)
TARGET_RMS: float = 0.15

# Máxima ganancia de normalización para evitar amplificar ruido de fondo
MAX_NORMALIZE_GAIN_DB: float = 12.0

# Umbral mínimo de pico para considerar que un fragmento tiene señal válida
MIN_PEAK: float = 1e-4


@dataclass(frozen=True)
class FragmentQuality:
    """Resultado del análisis de calidad de un fragmento de audio."""

    peak: float
    rms: float
    dc_offset: float
    clipped_samples: int
    duration_s: float
    has_signal: bool
    anomaly_flags: list[str]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Funciones de procesamiento individual
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def remove_dc_offset(audio: np.ndarray) -> np.ndarray:
    """Elimina el offset DC (componente de frecuencia cero) del audio.

    Un DC offset no deseado puede causar clicks al concatenar fragmentos
    y reducir el headroom disponible antes del clipping.
    """
    audio = np.asarray(audio, dtype=np.float32)
    if audio.size == 0:
        return audio
    mean = float(np.mean(audio))
    if abs(mean) < 1e-7:
        return audio
    return (audio - mean).astype(np.float32)


def soft_clip(audio: np.ndarray, threshold: float = CLIP_THRESHOLD) -> np.ndarray:
    """Aplica un soft-clip suave para prevenir distorsión por saturación.

    Las muestras que exceden el umbral se comprimen suavemente en lugar de
    recortarse bruscamente, preservando armónicas y reduciendo distorsión
    audible.
    """
    audio = np.asarray(audio, dtype=np.float32)
    if audio.size == 0:
        return audio

    # Mapeo suave: valores por debajo del umbral pasan sin cambios;
    # valores por encima se comprimen con una curva tangente hiperbólica.
    over = np.abs(audio) > threshold
    if not np.any(over):
        return audio

    sign = np.sign(audio)
    mag = np.abs(audio)
    compressed = threshold + (1.0 - threshold) * np.tanh((mag - threshold) / (1.0 - threshold))
    compressed = np.clip(compressed, 0.0, 1.0)
    result = np.where(over, sign * compressed, audio)
    return result.astype(np.float32)


def fade_in_out(
    audio: np.ndarray,
    sr: int,
    fade_ms: float = FADE_MS,
) -> np.ndarray:
    """Aplica fade in y fade out suaves para eliminar clicks en los bordes.

    Los fragments de TTS pueden iniciar o terminar con transiciones bruscas
    que generan clicks audibles al concatenarse. Un fade muy corto (5 ms)
    es imperceptible pero elimina la mayoría de los clicks.
    """
    audio = np.asarray(audio, dtype=np.float32)
    n = len(audio)
    if n == 0:
        return audio

    fade_samples = int(sr * fade_ms / 1000.0)
    fade_samples = min(fade_samples, n // 2)
    if fade_samples < 1:
        return audio

    # Curva de fade sinusoidal al cuadrado (más suave que lineal)
    ramp = np.sin(np.linspace(0, np.pi / 2, fade_samples)) ** 2
    result = audio.copy()
    result[:fade_samples] *= ramp
    result[-fade_samples:] *= ramp[::-1]
    return result.astype(np.float32)


def trim_silence_edges(
    audio: np.ndarray,
    sr: int,
    rms_ratio: float = SILENCE_RMS_RATIO,
    min_keep_s: float = 0.05,
) -> np.ndarray:
    """Elimina silencio anómalo al inicio y al final del fragmento.

    XTTS a veces genera silencio innecesario al principio o al final.
    Se recorta hasta encontrar señal por encima del umbral relativo,
    pero se conserva al menos min_keep_s de audio para no cortar
    ataques o colas de reverberación naturales.
    """
    audio = np.asarray(audio, dtype=np.float32)
    n = len(audio)
    if n == 0:
        return audio

    peak = float(np.max(np.abs(audio)))
    if peak < MIN_PEAK:
        return audio  # fragmento en silencio, no recortar

    threshold = peak * rms_ratio
    # Envolvente simple: valor absoluto suavizado por ventana móvil
    window = max(int(sr * 0.01), 1)  # ventanas de 10 ms
    if window >= n:
        return audio

    # Calcular RMS por ventana usando convolución
    kernel = np.ones(window, dtype=np.float32) / window
    abs_audio = np.abs(audio)
    envelope = np.convolve(abs_audio, kernel, mode="same")

    # Encontrar bordes de señal
    above = np.where(envelope > threshold)[0]
    if len(above) == 0:
        return audio

    first = int(above[0])
    last = int(above[-1])

    # Conservar margen mínimo
    min_samples = int(sr * min_keep_s)
    start = max(0, first - min_samples)
    end = min(n, last + min_samples + 1)

    return audio[start:end].astype(np.float32)


def rms_normalize(
    audio: np.ndarray,
    target_rms: float = TARGET_RMS,
    max_gain_db: float = MAX_NORMALIZE_GAIN_DB,
) -> np.ndarray:
    """Normaliza la ganancia del audio a un nivel RMS objetivo.

    Esto asegura que todos los fragmentos tengan un volumen percibido
    consistente, evitando saltos bruscos entre capítulos o narraciones.
    Se limita la ganancia máxima para no amplificar ruido de fondo.
    """
    audio = np.asarray(audio, dtype=np.float32)
    if audio.size == 0:
        return audio

    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < 1e-8:
        return audio  # silencio, no amplificar

    target_rms = max(target_rms, 1e-8)
    gain = target_rms / rms

    # Limitar ganancia máxima para no amplificar ruido
    max_gain_linear = 10.0 ** (max_gain_db / 20.0)
    gain = min(gain, max_gain_linear)

    result = audio * gain
    return np.clip(result, -1.0, 1.0).astype(np.float32)


def detect_clipping(audio: np.ndarray, threshold: float = CLIP_THRESHOLD) -> int:
    """Cuenta el número de muestras en clipping (valor absoluto >= umbral)."""
    audio = np.asarray(audio, dtype=np.float32)
    return int(np.count_nonzero(np.abs(audio) >= threshold))


def analyze_fragment_quality(
    audio: np.ndarray,
    sr: int,
) -> FragmentQuality:
    """Analiza la calidad de un fragmento de audio y detecta anomalías.

    Retorna un objeto FragmentQuality con métricas y flags de anomalía
    que pueden usarse para decidir si regenerar el fragmento.
    """
    audio = np.asarray(audio, dtype=np.float32)
    n = len(audio)
    duration_s = n / sr if sr > 0 else 0.0

    peak = float(np.max(np.abs(audio))) if n else 0.0
    rms = float(np.sqrt(np.mean(audio ** 2))) if n else 0.0
    dc_offset = float(np.mean(audio)) if n else 0.0
    clipped = detect_clipping(audio)
    has_signal = peak >= MIN_PEAK

    flags: list[str] = []
    if clipped > 0:
        flags.append(f"clipping:{clipped} muestras")
    if abs(dc_offset) > 0.01:
        flags.append(f"dc_offset:{dc_offset:.4f}")
    if peak < MIN_PEAK:
        flags.append("sin_signal")
    if rms < 1e-4 and has_signal:
        flags.append("rms_muy_bajo")
    if duration_s < 0.1 and has_signal:
        flags.append("duracion_muy_corta")

    return FragmentQuality(
        peak=peak,
        rms=rms,
        dc_offset=dc_offset,
        clipped_samples=clipped,
        duration_s=duration_s,
        has_signal=has_signal,
        anomaly_flags=flags,
    )


def optimize_fragment(
    audio: np.ndarray,
    sr: int,
    *,
    target_rms: float = TARGET_RMS,
    fade_ms: float = FADE_MS,
    trim_edges: bool = True,
    remove_dc: bool = True,
    soft_limit: bool = True,
    normalize: bool = True,
) -> np.ndarray:
    """Aplica el pipeline completo de optimización a un fragmento de audio.

    Orden de operaciones:
    1. Eliminar DC offset
    2. Trimming de silencio en bordes
    3. Fade in/out (eliminar clicks)
    4. Normalización RMS (volumen consistente)
    5. Soft-clip (prevenir distorsión)

    Esta función es segura para aplicar a cada fragmento antes de cachearlo.
    """
    audio = np.asarray(audio, dtype=np.float32).copy()

    if audio.size == 0:
        return audio

    # 1. Eliminar DC offset
    if remove_dc:
        audio = remove_dc_offset(audio)

    # 2. Trimming de silencio en bordes
    if trim_edges:
        audio = trim_silence_edges(audio, sr)

    if audio.size == 0:
        return audio

    # 3. Fade in/out para eliminar clicks en bordes
    if fade_ms > 0:
        audio = fade_in_out(audio, sr, fade_ms)

    # 4. Normalización RMS para volumen consistente
    if normalize:
        audio = rms_normalize(audio, target_rms=target_rms)

    # 5. Soft-clip final para prevenir distorsión
    if soft_limit:
        audio = soft_clip(audio)

    return audio.astype(np.float32)


def crossfade_fragments(
    parts: list[np.ndarray],
    sr: int,
    crossfade_ms: float = 10.0,
) -> np.ndarray:
    """Une múltiples fragmentos de audio con crossfade suave entre ellos.

    Esto elimina los clicks y saltos que ocurren al concatenar fragmentos
    de TTS directamente. Cada unión tiene un crossfade de crossfade_ms
    donde el final de un fragmento se desvanece mientras el siguiente
    se introduce.

    Args:
        parts: Lista de arrays de audio (float32).
        sr: Sample rate en Hz.
        crossfade_ms: Duración del crossfade en milisegundos.

    Returns:
        Array de audio concatenado con crossfades aplicados.
    """
    parts = [np.asarray(p, dtype=np.float32) for p in parts if p is not None and len(p) > 0]
    if not parts:
        return np.zeros(0, dtype=np.float32)
    if len(parts) == 1:
        return parts[0]

    cf_samples = int(sr * crossfade_ms / 1000.0)
    if cf_samples < 1:
        return np.concatenate(parts).astype(np.float32)

    # Curva de crossfade: coseno al cuadrado (potencia constante)
    ramp = np.sin(np.linspace(0, np.pi / 2, cf_samples)) ** 2
    ramp_out = ramp[::-1]

    result = parts[0].copy()
    for i in range(1, len(parts)):
        prev = result
        curr = parts[i]

        # Asegurar que tenemos suficientes muestras para el crossfade
        cf_len = min(cf_samples, len(prev), len(curr))
        if cf_len < 1:
            result = np.concatenate([result, curr]).astype(np.float32)
            continue

        # Aplicar crossfade en la unión
        overlap_prev = prev[-cf_len:] * ramp_out[:cf_len]
        overlap_curr = curr[:cf_len] * ramp[:cf_len]
        overlap = overlap_prev + overlap_curr

        # Construir resultado: prev[:-cf_len] + overlap + curr[cf_len:]
        new_parts = []
        if len(prev) > cf_len:
            new_parts.append(prev[:-cf_len])
        new_parts.append(overlap)
        if len(curr) > cf_len:
            new_parts.append(curr[cf_len:])
        result = np.concatenate(new_parts).astype(np.float32)

    return result


def normalize_loudness_ebu_r128(
    audio: np.ndarray,
    sr: int,
    target_lufs: float = -16.0,
) -> np.ndarray:
    """Normalización de loudness simplificada en dominio del tiempo.

    Esta es una aproximación rápida de EBU R128 que no requiere ffmpeg.
    Ajusta la ganancia basada en el RMS estimado para acercarse al
    LUFS objetivo. Para producción final, usar voicefx.normalize_lufs
    con ffmpeg loudnorm (dos pasadas).

    Útil para normalización rápida de fragmentos individuales.
    """
    audio = np.asarray(audio, dtype=np.float32)
    if audio.size == 0:
        return audio

    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < 1e-8:
        return audio

    # Conversión aproximada: LUFS ≈ 20*log10(RMS) + K (K ≈ -0.691 para K-weighting simplificado)
    # Usamos una aproximación conservadora
    current_lufs = 20.0 * np.log10(rms + 1e-12) - 0.691
    gain_db = target_lufs - current_lufs

    # Limitar ganancia para evitar amplificar ruido excesivamente
    gain_db = np.clip(gain_db, -24.0, 12.0)
    gain_linear = 10.0 ** (gain_db / 20.0)

    result = audio * gain_linear
    return np.clip(result, -1.0, 1.0).astype(np.float32)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Funciones de conveniencia para pipeline
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def prepare_audio_for_cache(
    audio: np.ndarray,
    sr: int,
    settings=None,
) -> np.ndarray:
    """Prepara un fragmento de audio para ser cacheado.

    Aplica todas las optimizaciones necesarias para asegurar que el audio
    en caché tenga calidad consistente y esté listo para concatenarse.

    Args:
        audio: Array de audio float32.
        sr: Sample rate.
        settings: Objeto Settings de VoxForge (opcional, usa valores por defecto si None).

    Returns:
        Array de audio optimizado listo para cachear.
    """
    target_rms = TARGET_RMS
    fade_ms = FADE_MS
    max_gain_db = MAX_NORMALIZE_GAIN_DB

    if settings is not None:
        target_rms = getattr(settings, "target_rms", TARGET_RMS)
        fade_ms = getattr(settings, "fade_ms", FADE_MS)
        max_gain_db = getattr(settings, "max_normalize_gain_db", MAX_NORMALIZE_GAIN_DB)

    return optimize_fragment(
        audio,
        sr,
        target_rms=target_rms,
        fade_ms=fade_ms,
        trim_edges=True,
        remove_dc=True,
        soft_limit=True,
        normalize=True,
    )


def assemble_final_audio(
    parts: list[np.ndarray],
    sr: int,
    crossfade_ms: float = 10.0,
) -> np.ndarray:
    """Ensambla el audio final de múltiples fragmentos con crossfade.

    Esta es la función recomendada para unir los fragmentos de una
    narración completa. Aplica crossfade entre cada par de fragmentos
    para eliminar clicks y saltos en las uniones.
    """
    return crossfade_fragments(parts, sr, crossfade_ms=crossfade_ms)
