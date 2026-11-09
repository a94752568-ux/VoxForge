"""Rutas y ajustes de VoxForge Local."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def home() -> Path:
    """Carpeta de datos (muestras, caché, exportaciones, base de datos).

    Por defecto ~/VoxForge/data; se puede cambiar con la variable VOXFORGE_HOME.
    """
    base = os.environ.get("VOXFORGE_HOME")
    path = Path(base).expanduser() if base else Path.home() / "VoxForge" / "data"
    for sub in ("voices", "cache", "exports"):
        (path / sub).mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Settings:
    language: str = "es"
    max_chunk_chars: int = 220      # XTTS en español admite ~239 caracteres por fragmento
    pause_ms: int = 350             # silencio entre fragmentos
    paragraph_pause_ms: int = 800   # silencio al final de un párrafo
    threads: int = 2                # hilos de torch (el equipo tiene 2 núcleos físicos)
    thermal_guard: bool = False     # opcional y desactivada: solo mide entre fragmentos (ver thermal.py)
    temp_pause_c: float = 90.0      # si la guardia está activa: pausa al superar esta temperatura
    temp_resume_c: float = 80.0     # y reanuda al bajar de esta
    # Control de calidad de cada fragmento (valores provisionales, ajustables):
    # velocidad de habla en caracteres por segundo; fuera de rango = fragmento anómalo
    rate_min_cps: float = 6.0       # medido: normales 8-12 car/s, anómalo 4,9 car/s
    rate_max_cps: float = 20.0
    max_retries: int = 2            # reintentos con otra semilla si un fragmento sale anómalo
    
    # =========================================================================
    # Configuración de optimización de audio profesional
    # =========================================================================
    # Post-procesamiento por fragmento para reducir anomalías en el audio final
    target_rms: float = 0.15        # Nivel RMS objetivo para normalización entre fragmentos
    fade_ms: float = 5.0            # Duración de fade in/out en ms (eliminar clicks en bordes)
    crossfade_ms: float = 10.0      # Crossfade entre fragmentos en ms (uniones suaves)
    max_normalize_gain_db: float = 12.0  # Ganancia máxima de normalización (evitar amplificar ruido)
    
    # =========================================================================
    # Configuración de audio profesional (EBU R128)
    # =========================================================================
    # Normalización de loudness (EBU R128 para audiolibros: -16 LUFS)
    target_lufs: float = -16.0      # Nivel de loudness integrado objetivo
    target_true_peak: float = -1.5  # Pico verdadero máximo permitido (dB TP)
    target_lra: float = 11.0        # Rango dinámico objetivo (LU)
    apply_ebu_r128: bool = True     # Aplicar normalización EBU R128 por defecto
    
    # Preset de FX por defecto para narraciones
    default_fx_preset: str | None = None  # None = sin FX, "audiolibro_pro" para producción
    
    # Configuración de reducción de ruido y de-essing
    noise_gate_threshold: float = -40.0  # Umbral para noise gate (dB)
    deesser_frequency: float = 4000.0  # Frecuencia central para de-esser (Hz)
    deesser_gain: float = -2.0        # Reducción de sibilantes (dB)
    
    # =========================================================================
    # Auto-unload del modelo para ahorrar RAM
    # =========================================================================
    auto_unload: bool = True          # Descargar modelo automáticamente después de inactividad
    auto_unload_minutes: int = 10     # Minutos de inactividad antes de descargar
    last_activity_time: float = 0.0   # Timestamp de última actividad (no serializar)


def load_settings(data_dir: Path) -> Settings:
    """Lee data/config.json; si no existe lo crea con los valores por defecto.
    
    También aplica migraciones para nuevas opciones de configuración.
    """
    cfg = data_dir / "config.json"
    if not cfg.exists():
        settings = Settings()
        cfg.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
        return settings
    
    raw = json.loads(cfg.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Settings)}
    
    # Aplicar valores por defecto para nuevas opciones
    loaded_settings = {}
    for k, v in raw.items():
        if k in known:
            loaded_settings[k] = v
    
    # Crear Settings con los valores cargados
    settings = Settings(**loaded_settings)
    
    # Guardar si hay nuevas opciones que no estaban en el archivo
    current_dict = asdict(settings)
    if set(current_dict.keys()) != set(raw.keys()):
        cfg.write_text(json.dumps(current_dict, indent=2), encoding="utf-8")
    
    return settings


# =============================================================================
# Integración con Pydantic (opcional, requiere pydantic)
# =============================================================================

def load_settings_pydantic(data_dir: Path) -> "Settings | Any":
    """Carga la configuración usando Pydantic para validación avanzada.
    
    Esta función requiere que pydantic esté instalado:
        pip install pydantic pydantic-settings
    
    Si pydantic no está disponible, cae a la versión dataclass.
    
    Args:
        data_dir: Directorio de datos donde se encuentra config.json.
    
    Returns:
        Instancia de Settings (Pydantic) o Settings (dataclass) si pydantic no está disponible.
    """
    try:
        from .config_pydantic import load_settings_pydantic as _load_pydantic, Settings as PydanticSettings
        return _load_pydantic(data_dir)
    except ImportError:
        # Fallback a dataclass
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Pydantic no está disponible, usando dataclass")
        return load_settings(data_dir)
