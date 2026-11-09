"""Utilidades comunes para VoxForge Local."""
from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable, TypeVar

T = TypeVar("T")


# =============================================================================
# Subprocess utilities
# =============================================================================

logger = logging.getLogger(__name__)


def run_command(
    cmd: list[str],
    capture_output: bool = True,
    text: bool = True,
    timeout: float | None = None,
    cwd: Path | str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Ejecuta un comando con subprocess.run usando check=True por defecto.
    
    Args:
        cmd: Lista de argumentos del comando.
        capture_output: Si True, captura stdout y stderr.
        text: Si True, devuelve strings en lugar de bytes.
        timeout: Timeout en segundos.
        cwd: Directorio de trabajo.
        check: Si True, levanta CalledProcessError si el comando falla.
    
    Returns:
        subprocess.CompletedProcess con los resultados.
    
    Raises:
        subprocess.CalledProcessError: Si check=True y el comando falla.
        subprocess.TimeoutExpired: Si el comando excede el timeout.
    """
    try:
        return subprocess.run(
            cmd,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            cwd=cwd,
            check=check,
        )
    except subprocess.TimeoutExpired as e:
        logger.error(f"Comando excedio timeout: {' '.join(cmd)}")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"Comando fallo: {' '.join(cmd)}")
        if e.stderr:
            logger.error(f"stderr: {e.stderr}")
        raise


# =============================================================================
# Excepciones personalizadas
# =============================================================================

class VoxForgeError(Exception):
    """Excepción base para todos los errores de VoxForge."""
    pass


class DiskSpaceError(VoxForgeError):
    """No hay suficiente espacio en disco."""
    def __init__(self, path: Path, required_bytes: int, available_bytes: int):
        self.path = path
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes
        required_gb = required_bytes / (1024**3)
        available_gb = available_bytes / (1024**3)
        super().__init__(
            f"Espacio insuficiente en {path.parent}: "
            f"necesitas {required_gb:.2f} GB, disponibles {available_gb:.2f} GB"
        )


class ValidationError(VoxForgeError):
    """Error de validación de entradas."""
    pass


class ConfigurationError(VoxForgeError):
    """Error de configuración."""
    pass


class ModelUnavailableError(VoxForgeError):
    """El modelo de TTS no está disponible."""
    pass


class SynthCancelledError(VoxForgeError):
    """La síntesis de voz fue cancelada."""
    pass


# =============================================================================
# Validación de espacio en disco
# =============================================================================

def check_disk_space(
    path: Path,
    required_bytes: int,
    safety_factor: float = 1.5
) -> None:
    """Verifica que hay suficiente espacio en disco.
    
    Args:
        path: Path donde se escribirán los datos (se usa para determinar la partición).
        required_bytes: Bytes necesarios.
        safety_factor: Margen de seguridad (1.5 = 50% adicional).
    
    Raises:
        DiskSpaceError: Si no hay suficiente espacio.
    """
    try:
        total, used, free = shutil.disk_usage(path.parent)
    except Exception as e:
        raise DiskSpaceError(path, required_bytes, 0) from e
    
    if free < required_bytes * safety_factor:
        raise DiskSpaceError(path, int(required_bytes * safety_factor), free)


# =============================================================================
# Estimación de tamaño de audio
# =============================================================================

def estimate_audio_size_bytes(
    text_chars: int,
    sample_rate: int = 24000,
    bits_per_sample: int = 16,
    channels: int = 1,
    cps: float = 10.0  # caracteres por segundo
) -> int:
    """Estima el tamaño en bytes de un audio generado a partir de texto.
    
    Args:
        text_chars: Número de caracteres en el texto.
        sample_rate: Frecuencia de muestreo en Hz.
        bits_per_sample: Bits por muestra.
        channels: Número de canales.
        cps: Caracteres por segundo (velocidad de habla estimada).
    
    Returns:
        Tamaño estimado en bytes.
    """
    if cps <= 0:
        return 0
    duration_seconds = text_chars / cps
    bytes_per_second = sample_rate * channels * (bits_per_sample // 8)
    return int(duration_seconds * bytes_per_second)


# =============================================================================
# Utilidades de cancelación
# =============================================================================

class CancellationToken:
    """Token para cancelación cooperativa de operaciones largas."""
    
    def __init__(self):
        self._cancelled = threading.Event()
    
    @property
    def is_cancelled(self) -> bool:
        """Indica si la operación debe cancelarse."""
        return self._cancelled.is_set()
    
    def cancel(self) -> None:
        """Solicita la cancelación."""
        self._cancelled.set()
    
    def check(self) -> None:
        """Verifica si se ha solicitado cancelación.
        
        Raises:
            SynthCancelledError: Si la operación fue cancelada.
        """
        if self.is_cancelled:
            raise SynthCancelledError("Operación cancelada por el usuario")


# =============================================================================
# Utilidades de paths
# =============================================================================

def sanitize_path(path: Path) -> Path:
    """Normaliza y valida un path para evitar problemas de seguridad.
    
    Args:
        path: Path a sanitizar.
    
    Returns:
        Path sanitizado y resuelto.
    
    Raises:
        ValidationError: Si el path no es válido.
    """
    if not path:
        raise ValidationError("Path no puede ser vacío")
    
    # Resolver path relativo y expandir ~
    try:
        resolved = Path(path).expanduser().resolve()
    except Exception as e:
        raise ValidationError(f"Path inválido: {path}") from e
    
    # Verificar que no contenga componentes sospechosos
    parts = resolved.parts
    if ".." in parts:
        raise ValidationError(f"Path contiene componentes no válidos: {path}")
    
    return resolved


def ensure_directory(path: Path) -> None:
    """Asegura que un directorio exista, creándolo si es necesario.
    
    Args:
        path: Path del directorio.
    """
    path.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Validación de integridad de archivos de audio
# =============================================================================

class AudioValidationError(VoxForgeError):
    """Archivo de audio corrupto o inválido."""
    pass


def validate_audio_file(
    path: Path,
    min_duration_seconds: float = 0.05,
    max_duration_seconds: float | None = None,
    require_non_silent: bool = True,
) -> dict:
    """Valida que un archivo de audio sea legible y tenga datos válidos.
    
    Verifica:
    - El archivo existe y tiene tamaño > 0
    - Puede ser leído por soundfile (formato WAV/FLAC válido)
    - Tiene canales y sample rate válidos
    - La duración está dentro de los límites esperados
    - No contiene valores NaN o Inf
    - Opcionalmente: no está completamente en silencio
    
    Args:
        path: Path al archivo de audio.
        min_duration_seconds: Duración mínima aceptable (segundos).
        max_duration_seconds: Duración máxima aceptable (segundos, opcional).
        require_non_silent: Si True, rechaza audio que esté completamente en silencio.
    
    Returns:
        Dict con metadatos: {'duration': float, 'sample_rate': int, 'channels': int,
        'frames': int, 'samples': int, 'rms': float, 'peak': float}
    
    Raises:
        AudioValidationError: Si el archivo es inválido o corrupto.
    """
    import numpy as np
    import soundfile as sf
    
    path = Path(path)
    
    if not path.is_file():
        raise AudioValidationError(f"El archivo de audio no existe: {path}")
    
    file_size = path.stat().st_size
    if file_size == 0:
        raise AudioValidationError(f"El archivo de audio está vacío (0 bytes): {path}")
    
    # Umbral mínimo: un header WAV mínimo tiene ~44 bytes
    if file_size < 100:
        raise AudioValidationError(
            f"El archivo de audio es demasiado pequeño ({file_size} bytes), "
            f"probablemente corrupto: {path}"
        )
    
    try:
        info = sf.info(path)
    except Exception as exc:
        raise AudioValidationError(
            f"No se puede leer el archivo de audio (posiblemente corrupto): {path} "
            f"({exc})"
        ) from exc
    
    # Validar metadatos básicos
    if info.samplerate <= 0 or info.samplerate > 192000:
        raise AudioValidationError(
            f"Sample rate inválido: {info.samplerate} Hz en {path}"
        )
    if info.channels <= 0 or info.channels > 8:
        raise AudioValidationError(
            f"Número de canales inválido: {info.channels} en {path}"
        )
    if info.frames <= 0:
        raise AudioValidationError(
            f"El archivo no contiene frames de audio: {path}"
        )
    
    duration = float(info.frames) / float(info.samplerate)
    
    if duration < min_duration_seconds:
        raise AudioValidationError(
            f"Duración demasiado corta ({duration:.3f}s < {min_duration_seconds}s): {path}"
        )
    
    if max_duration_seconds is not None and duration > max_duration_seconds:
        raise AudioValidationError(
            f"Duración demasiado larga ({duration:.3f}s > {max_duration_seconds}s): {path}"
        )
    
    # Leer datos y validar contenido
    try:
        data, _ = sf.read(path, dtype="float32")
    except Exception as exc:
        raise AudioValidationError(
            f"No se pueden leer los datos de audio (corrupto): {path} ({exc})"
        ) from exc
    
    if data.size == 0:
        raise AudioValidationError(
            f"El archivo de audio no contiene muestras: {path}"
        )
    
    # Verificar NaN/Inf
    if not np.all(np.isfinite(data)):
        raise AudioValidationError(
            f"El archivo contiene valores NaN o Inf: {path}"
        )
    
    # Calcular RMS y pico
    data_flat = data.reshape(-1) if data.ndim > 1 else data
    rms = float(np.sqrt(np.mean(data_flat ** 2)))
    peak = float(np.max(np.abs(data_flat)))
    
    # Verificar que no esté completamente en silencio
    if require_non_silent and peak < 1e-6:
        raise AudioValidationError(
            f"El archivo de audio está en silencio (pico={peak:.2e}): {path}"
        )
    
    return {
        "duration": duration,
        "sample_rate": int(info.samplerate),
        "channels": int(info.channels),
        "frames": int(info.frames),
        "samples": int(data.size),
        "rms": rms,
        "peak": peak,
    }


def validate_wav_not_corrupt(path: Path) -> None:
    """Validación rápida: lanzar excepción si el WAV es corrupto o inválido.
    
    Versión simplificada para usar en bucles calientes donde no se necesitan
    todos los metadatos.
    
    Args:
        path: Path al archivo de audio.
    
    Raises:
        AudioValidationError: Si el archivo es inválido.
    """
    validate_audio_file(path, require_non_silent=False)
