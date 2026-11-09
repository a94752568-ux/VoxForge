"""Configuración de VoxForge Local usando Pydantic v2.

Este módulo proporciona una configuración validada usando Pydantic.

Beneficios sobre dataclasses:
- Validación automática de tipos
- Valores por defecto
- Serialización/deserialización automática
- Documentación automática
- Soporte para JSON Schema

Uso:
    from voxforge.config_pydantic import Settings
    
    # Crear con valores por defecto
    settings = Settings()
    
    # Crear desde dict
    settings = Settings(**dict_from_json)
    
    # Validar
    settings.model_validate(dict_from_json)

NOTA: Este módulo requiere Pydantic v2 y pydantic-settings.
      Instálalos con: pip install pydantic pydantic-settings
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Literal, Any

logger = logging.getLogger(__name__)

try:
    from pydantic import BaseModel, Field, field_validator, model_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict
    PYDANTIC_AVAILABLE = True
except ImportError as e:
    PYDANTIC_AVAILABLE = False
    logger.warning(f"Pydantic no está disponible: {e}. Usa el config estándar.")
    BaseModel = None
    BaseSettings = None
    Field = None


# =============================================================================
# Configuración principal
# =============================================================================

if PYDANTIC_AVAILABLE:
    class Settings(BaseModel):
        """Configuración principal de VoxForge Local.
        
        Todos los campos son opcionales y tienen valores por defecto.
        """
        
        # -- Idioma y voz -----------------------------------------------------------
        language: str = Field(
            default="es",
            description="Idioma por defecto para la síntesis de voz",
            min_length=1,
            max_length=10,
        )
        voice_profile: str = Field(
            default="yo_limpia",
            description="Perfil de voz por defecto",
            min_length=1,
            max_length=60,
    )
    
    # -- Segmentación de texto --------------------------------------------------
    max_chunk_chars: int = Field(
        default=220,
        ge=50,
        le=500,
        description="Número máximo de caracteres por fragmento (XTTS en español admite ~239)",
    )
    
    # -- Pausas -----------------------------------------------------------------
    pause_ms: int = Field(
        default=350,
        ge=0,
        le=5000,
        description="Silencio entre fragmentos en milisegundos",
    )
    paragraph_pause_ms: int = Field(
        default=800,
        ge=0,
        le=5000,
        description="Silencio al final de un párrafo en milisegundos",
    )
    
    # -- Rendimiento ------------------------------------------------------------
    threads: int = Field(
        default=2,
        ge=1,
        le=16,
        description="Número de hilos de torch (recomendado: número de núcleos físicos)",
    )
    
    # -- Protección térmica ------------------------------------------------------
    thermal_guard: bool = Field(
        default=False,
        description="Activar protección térmica (pausa si la CPU está muy caliente)",
    )
    temp_pause_c: float = Field(
        default=90.0,
        ge=40.0,
        le=120.0,
        description="Temperatura a la cual pausar (en °C)",
    )
    temp_resume_c: float = Field(
        default=80.0,
        ge=30.0,
        le=110.0,
        description="Temperatura a la cual reanudar (en °C)",
    )
    
    # -- Control de calidad ------------------------------------------------------
    rate_min_cps: float = Field(
        default=6.0,
        ge=1.0,
        le=50.0,
        description="Velocidad mínima de habla en caracteres por segundo (fragmentos anómalos)",
    )
    rate_max_cps: float = Field(
        default=20.0,
        ge=1.0,
        le=100.0,
        description="Velocidad máxima de habla en caracteres por segundo (fragmentos anómalos)",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Número máximo de reintentos para fragmentos anómalos",
    )
    
    # -- Normalización EBU R128 -------------------------------------------------
    target_lufs: float = Field(
        default=-16.0,
        ge=-70.0,
        le=0.0,
        description="Nivel de loudness integrado objetivo (EBU R128 recomienda -23)",
    )
    target_true_peak: float = Field(
        default=-1.5,
        ge=-20.0,
        le=0.0,
        description="Pico verdadero máximo permitido en dB TP",
    )
    target_lra: float = Field(
        default=11.0,
        ge=1.0,
        le=30.0,
        description="Rango dinámico objetivo en LU",
    )
    apply_ebu_r128: bool = Field(
        default=True,
        description="Aplicar normalización EBU R128 por defecto",
    )
    
    # -- Efectos de voz ----------------------------------------------------------
    default_fx_preset: str | None = Field(
        default=None,
        description="Preset de FX por defecto para narraciones (None = sin FX)",
    )
    noise_gate_threshold: float = Field(
        default=-40.0,
        ge=-120.0,
        le=0.0,
        description="Umbral para noise gate en dB",
    )
    deesser_frequency: float = Field(
        default=4000.0,
        ge=1000.0,
        le=10000.0,
        description="Frecuencia central para de-esser en Hz",
    )
    deesser_gain: float = Field(
        default=-2.0,
        ge=-20.0,
        le=0.0,
        description="Reducción de sibilantes en dB",
    )
    
    # -- Auto-unload del modelo -------------------------------------------------
    auto_unload: bool = Field(
        default=True,
        description="Descargar modelo automáticamente después de inactividad",
    )
    auto_unload_minutes: int = Field(
        default=10,
        ge=1,
        le=120,
        description="Minutos de inactividad antes de descargar el modelo",
    )
    
    # -- Directorios -----------------------------------------------------------
    cache_dir: Path | None = Field(
        default=None,
        description="Directorio de caché (None = usar data_dir/cache)",
    )
    export_dir: Path | None = Field(
        default=None,
        description="Directorio de exportación (None = usar data_dir/exports)",
    )
    
    # ---------------------------------------------------------------------------
    # Validaciones
    # ---------------------------------------------------------------------------
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validar código de idioma."""
        if not v.isalpha():
            raise ValueError("El código de idioma debe contener solo letras")
        return v.lower()
    
    @field_validator('temp_pause_c', 'temp_resume_c')
    @classmethod
    def validate_temperatures(cls, v: float) -> float:
        """Validar que las temperaturas sean realistas."""
        if v < 0 or v > 150:
            raise ValueError("Temperatura debe estar entre 0°C y 150°C")
        return v
    
    @model_validator(mode='after')
    def validate_temp_order(self) -> 'Settings':
        """Validar que temp_pause > temp_resume."""
        if self.thermal_guard and self.temp_pause_c <= self.temp_resume_c:
            raise ValueError("temp_pause_c debe ser mayor que temp_resume_c")
        return self


# =============================================================================
# Fin de la clase Settings - Cierre del bloque PYDANTIC_AVAILABLE
# =============================================================================


if PYDANTIC_AVAILABLE:
    # =============================================================================
    # Carga y guarda configuración
    # =============================================================================
    
    def home() -> Path:
        """Carpeta de datos de VoxForge Local."""
        base = os.environ.get("VOXFORGE_HOME")
        path = Path(base).expanduser() if base else Path.home() / "VoxForge" / "data"
        for sub in ("voices", "cache", "exports"):
            (path / sub).mkdir(parents=True, exist_ok=True)
        return path

    def load_settings_pydantic(data_dir: Path) -> Settings:
        """Carga la configuración desde un archivo JSON usando Pydantic.
        
        Args:
            data_dir: Directorio de datos donde se encuentra config.json.
        
        Returns:
            Instancia de Settings con los valores cargados.
        """
        cfg_path = data_dir / "config.json"
        
        if not cfg_path.exists():
            # Crear configuración por defecto
            settings = Settings()
            cfg_path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
            return settings
        
        # Cargar y validar
        with open(cfg_path, encoding="utf-8") as f:
            raw = json.load(f)
        
        try:
            settings = Settings(**raw)
            # Guardar con formato actualizado (incluyendo nuevos campos)
            cfg_path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
            return settings
        except Exception as e:
            # Si falla la validación, usar valores por defecto
            logger.error(f"Error al cargar configuración: {e}")
            logger.info("Usando valores por defecto")
            return Settings()

    def save_settings(settings: Settings, data_dir: Path) -> None:
        """Guarda la configuración a un archivo JSON.
        
        Args:
            settings: Configuración a guardar.
            data_dir: Directorio de datos donde guardar config.json.
        """
        cfg_path = data_dir / "config.json"
        cfg_path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")


    # =============================================================================
    # Compatibilidad
    # =============================================================================
    
    def migrate_from_dataclass(old_settings: 'SettingsDataclass') -> Settings:
        """Migra desde la antigua configuración con dataclasses.
        
        Args:
            old_settings: Instancia de la antigua clase Settings (dataclass).
        
        Returns:
            Instancia de Settings (Pydantic).
        """
        data = {}
        for field in old_settings.__dataclass_fields__:
            value = getattr(old_settings, field.name)
            # Convertir Path a str para JSON
            if isinstance(value, Path):
                value = str(value)
            data[field.name] = value
        
        return Settings(**data)


# =============================================================================
# Fin del bloque PYDANTIC_AVAILABLE
# =============================================================================
