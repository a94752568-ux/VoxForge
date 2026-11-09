"""Gestor de motores TTS con auto-unload para ahorrar RAM.

Este módulo proporciona:
- Carga perezosa del motor TTS
- Descarga automática después de inactividad
- Control de tiempo de última actividad
- Singleton para compartir el motor entre diferentes componentes
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .config import Settings

if TYPE_CHECKING:
    from .engines.base import TTSEngine

logger = logging.getLogger(__name__)


@dataclass
class EngineStatus:
    """Estado del motor TTS."""
    engine: TTSEngine | None = None
    loaded: bool = False
    last_activity: float = 0.0
    lock: threading.Lock = threading.Lock()


class EngineManager:
    """Gestor de motores TTS con auto-unload.
    
    Proporciona:
    - Carga perezosa del motor
    - Descarga automática después de inactividad
    - Singleton para compartir el motor entre componentes
    - Thread-safe
    """
    
    _instance: EngineManager | None = None
    _lock = threading.Lock()
    
    def __new__(cls, settings: Settings | None = None):
        """Singleton pattern."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, settings: Settings | None = None):
        """Inicializa el gestor de motores.
        
        Args:
            settings: Configuración de VoxForge.
        """
        if self._initialized:
            return
        
        self.settings = settings or Settings()
        self._status = EngineStatus()
        self._unload_timer: threading.Timer | None = None
        self._initialized = True
        
        logger.debug(f"EngineManager inicializado: auto_unload={self.settings.auto_unload}, "
                    f"auto_unload_minutes={self.settings.auto_unload_minutes}")
    
    # ---------------------------------------------------------------------------
    # Acceso al motor
    # ---------------------------------------------------------------------------
    
    def get_engine(self) -> TTSEngine:
        """Obtiene el motor TTS, cargándolo si es necesario.
        
        Returns:
            El motor TTS cargado y listo para usar.
        """
        with self._status.lock:
            if self._status.engine is None:
                self._status.engine = self._create_engine()
            
            if not self._status.loaded:
                logger.debug("Cargando el motor TTS...")
                self._status.engine.load()
                self._status.loaded = True
            
            # Actualizar tiempo de última actividad
            self._status.last_activity = time.time()
            self._update_unload_timer()
            
            return self._status.engine
    
    def _create_engine(self) -> TTSEngine:
        """Crea una nueva instancia del motor TTS."""
        from .engines.xtts import XttsEngine
        return XttsEngine(
            threads=self.settings.threads,
            offline=True
        )
    
    # ---------------------------------------------------------------------------
    # Descarga
    # ---------------------------------------------------------------------------
    
    def unload(self) -> None:
        """Descarga el motor TTS si está cargado."""
        with self._status.lock:
            if self._status.engine is not None and self._status.loaded:
                logger.debug("Descargando el motor TTS...")
                try:
                    self._status.engine.unload()
                    self._status.loaded = False
                except Exception as e:
                    logger.error(f"Error al descargar el motor: {e}")
            
            self._cancel_unload_timer()
    
    def unload_if_idle(self) -> bool:
        """Descarga el motor si ha estado inactivo.
        
        Returns:
            True si se descargó el motor, False si no.
        """
        with self._status.lock:
            if not self.settings.auto_unload:
                return False
            
            current_time = time.time()
            idle_time = current_time - self._status.last_activity
            
            if idle_time >= (self.settings.auto_unload_minutes * 60):
                if self._status.loaded:
                    logger.info(f"Motor inactivo por {idle_time:.1f}s, descargando...")
                    self.unload()
                    return True
            
            return False
    
    # ---------------------------------------------------------------------------
    # Timer de auto-unload
    # ---------------------------------------------------------------------------
    
    def _update_unload_timer(self) -> None:
        """Actualiza o crea el timer de auto-unload."""
        self._cancel_unload_timer()
        
        if not self.settings.auto_unload:
            return
        
        # Programar la descarga después de auto_unload_minutes
        delay = self.settings.auto_unload_minutes * 60
        
        def unload_callback():
            """Callback para el timer de auto-unload."""
            if self.unload_if_idle():
                logger.info("Motor descargado automaticamente por inactividad")
        
        self._unload_timer = threading.Timer(delay, unload_callback)
        self._unload_timer.daemon = True  # El timer no bloquea la salida del programa
        self._unload_timer.start()
        
        logger.debug(f"Timer de auto-unload programado en {delay}s")
    
    def _cancel_unload_timer(self) -> None:
        """Cancela el timer de auto-unload."""
        if self._unload_timer is not None:
            self._unload_timer.cancel()
            self._unload_timer = None
            logger.debug("Timer de auto-unload cancelado")
    
    # ---------------------------------------------------------------------------
    # Registrar actividad
    # ---------------------------------------------------------------------------
    
    def record_activity(self) -> None:
        """Registra actividad del motor (resetea el timer de auto-unload)."""
        with self._status.lock:
            self._status.last_activity = time.time()
            self._update_unload_timer()
    
    # ---------------------------------------------------------------------------
    # Limpieza
    # ---------------------------------------------------------------------------
    
    def cleanup(self) -> None:
        """Limpia recursos del gestor."""
        self._cancel_unload_timer()
        self.unload()
        logger.debug("EngineManager limpiado")
    
    # ---------------------------------------------------------------------------
    # Utilidades
    # ---------------------------------------------------------------------------
    
    def is_loaded(self) -> bool:
        """Comprueba si el motor está cargado."""
        with self._status.lock:
            return self._status.loaded
    
    def get_last_activity_time(self) -> float:
        """Obtiene el timestamp de la última actividad."""
        with self._status.lock:
            return self._status.last_activity
    
    def get_idle_time(self) -> float:
        """Obtiene el tiempo de inactividad en segundos."""
        with self._status.lock:
            return time.time() - self._status.last_activity


# =============================================================================
# Funciones de conveniencia
# =============================================================================

# Instancia global (se inicializa con settings por defecto)
_engine_manager: EngineManager | None = None


def get_engine_manager(settings: Settings | None = None) -> EngineManager:
    """Obtiene o crea el EngineManager global.
    
    Args:
        settings: Configuración de VoxForge.
    
    Returns:
        El EngineManager singleton.
    """
    global _engine_manager
    if _engine_manager is None:
        _engine_manager = EngineManager(settings)
    return _engine_manager


def get_engine(settings: Settings | None = None) -> TTSEngine:
    """Obtiene el motor TTS usando el gestor.
    
    Args:
        settings: Configuración de VoxForge.
    
    Returns:
        El motor TTS cargado y listo para usar.
    """
    manager = get_engine_manager(settings)
    return manager.get_engine()


def unload_engine() -> None:
    """Descarga el motor TTS global."""
    global _engine_manager
    if _engine_manager is not None:
        _engine_manager.unload()
