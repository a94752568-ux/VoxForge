"""Servicio de narración de texto a voz."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..db import Store
from ..config import Settings
from ..engines.base import TTSEngine, ModelUnavailableError
from ..engines.xtts import XttsEngine
from ..pipeline import narrate as _pipeline_narrate, NarrationResult
from ..utils import (
    check_disk_space,
    estimate_audio_size_bytes,
    CancellationToken,
    SynthCancelledError,
    DiskSpaceError,
    ValidationError,
)

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


# =============================================================================
# DTOs (Data Transfer Objects)
# =============================================================================

@dataclass
class NarrationRequest:
    """Solicitud de narración."""
    project_name: str
    chapter_id: int
    text: str
    voice_profile_name: str
    language: str | None = None
    regen: bool = False
    out_path: Path | None = None
    cancel_event: threading.Event | None = None
    project_id: int | None = None  # ID interno para reanudación
    resume: bool = True  # Intentar reanudar si existe progreso


@dataclass
class NarrationResponse:
    """Respuesta de una solicitud de narración."""
    success: bool
    result: NarrationResult | None = None
    error: str | None = None
    message: str = ""
    partial: bool = False  # Indica si la narración fue parcial (cancelada)
    
    @property
    def data(self) -> dict[str, Any]:
        """Retorna los datos como diccionario."""
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "message": self.message,
            "partial": self.partial,
        }


# =============================================================================
# Servicio de Narración
# =============================================================================

class NarratorService:
    """Servicio de narración de texto a voz.
    
    Este servicio centraliza toda la lógica relacionada con la narración:
    - Validación de entradas
    - Carga de perfiles y proyectos
    - Ejecución del pipeline de narración
    - Manejo de errores
    - Reanudación de narraciones interrumpidas
    """
    
    def __init__(
        self,
        store: Store,
        settings: Settings,
        data_dir: Path,
        cache_dir: Path | None = None,
        export_dir: Path | None = None,
        engine: TTSEngine | None = None,  # Motor personalizado (para tests)
    ):
        """Inicializa el servicio de narración.
        
        Args:
            store: Store de SQLite para persistencia.
            settings: Configuración de VoxForge.
            data_dir: Directorio base de datos.
            cache_dir: Directorio de caché (opcional, por defecto data_dir/cache).
            export_dir: Directorio de exportación (opcional, por defecto data_dir/exports).
            engine: Motor TTS personalizado (para tests). Si None, se crea un XttsEngine.
        """
        self.store = store
        self.settings = settings
        self.data_dir = Path(data_dir)
        self.cache_dir = Path(cache_dir) if cache_dir else self.data_dir / "cache"
        self.export_dir = Path(export_dir) if export_dir else self.data_dir / "exports"
        self.custom_engine = engine  # Motor personalizado para tests
        
        # Asegurar que los directorios existan
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"NarratorService inicializado: cache={self.cache_dir}, exports={self.export_dir}")
    
    # ---------------------------------------------------------------------------
    # Validaciones
    # ---------------------------------------------------------------------------
    
    def _validate_text(self, text: str) -> None:
        """Valida que el texto no esté vacío."""
        if not text or not text.strip():
            raise ValidationError("El texto está vacío o contiene solo espacios")
    
    def _validate_profile(self, profile_name: str) -> sqlite3.Row:
        """Valida que el perfil de voz exista."""
        profile = self.store.get_profile(profile_name)
        if profile is None:
            raise ValidationError(
                f"Perfil de voz '{profile_name}' no encontrado. "
                "Crea el perfil primero con: voxforge voice add"
            )
        return profile
    
    def _validate_disk_space(self, text: str) -> None:
        """Valida que hay suficiente espacio en disco para la narración."""
        # Estimar tamaño del audio final
        estimated_size = estimate_audio_size_bytes(
            len(text),
            sample_rate=self.settings.threads * 12000,  # Estimación conservadora
            cps=self.settings.rate_min_cps
        )
        
        # Añadir margen para caché y archivos temporales
        required_space = estimated_size * 3  # 3x para margen de seguridad
        
        check_disk_space(self.export_dir, required_space)
    
    # ---------------------------------------------------------------------------
    # Narración
    # ---------------------------------------------------------------------------
    
    def narrate(self, request: NarrationRequest) -> NarrationResponse:
        """Ejecuta una narración completa.
        
        Args:
            request: Solicitud de narración.
        
        Returns:
            NarrationResponse con el resultado o error.
        """
        try:
            # Validar entradas
            self._validate_text(request.text)
            profile = self._validate_profile(request.voice_profile_name)
            
            # Validar espacio en disco
            self._validate_disk_space(request.text)
            
            # Determinar paths
            out_path = self._get_out_path(request)
            language = request.language or profile["language"]
            
            # Crear cancellation token
            cancel_token = CancellationToken()
            if request.cancel_event:
                def check_cancel():
                    if request.cancel_event.is_set():
                        cancel_token.cancel()
                
                # Verificar periódicamente (simplificación)
                # En la práctica, esto se manejaría en el pipeline
                pass
            
            # Crear motor TTS
            engine = self._create_engine()
            
            # Ejecutar pipeline de narración
            logger.info(
                f"Iniciando narración: proyecto={request.project_name}, "
                f"capítulo={request.chapter_id}, perfil={profile['name']}, "
                f"fragmentos estimados={len(request.text) // self.settings.max_chunk_chars}"
            )
            
            result = _pipeline_narrate(
                text=request.text,
                profile=profile,
                engine=engine,
                store=self.store,
                settings=self.settings,
                cache_dir=self.cache_dir,
                out_path=out_path,
                language=language,
                regen=request.regen,
                project_name=request.project_name,
                chapter_id=request.chapter_id,
                resume=request.resume,
                cancel_event=request.cancel_event,
            )
            
            logger.info(
                f"Narración completada: {result.fragments} fragmentos "
                f"({result.generated} generados, {result.cached} en caché), "
                f"duración={result.audio_s:.1f}s"
            )
            
            return NarrationResponse(
                success=True,
                result=result,
                message=f"Narración completada: {result.fragments} fragmentos generados"
            )
            
        except SynthCancelledError:
            logger.info("Narración cancelada por el usuario")
            return NarrationResponse(
                success=False,
                partial=True,
                error="Narración cancelada por el usuario",
                message="Puedes reanudar la narración más tarde"
            )
            
        except DiskSpaceError as e:
            logger.error(f"Error de espacio en disco: {e}")
            return NarrationResponse(
                success=False,
                error=f"Espacio en disco insuficiente: {e}",
                message="Libera espacio en disco y vuelve a intentarlo"
            )
            
        except ModelUnavailableError as e:
            logger.error(f"Modelo no disponible: {e}")
            return NarrationResponse(
                success=False,
                error=f"Modelo no disponible: {e}",
                message=(
                    "El modelo XTTS no está descargado o no se puede cargar. "
                    "Ejecuta: source .venv/bin/activate && python -m voxforge voice prepare"
                )
            )
            
        except ValidationError as e:
            logger.warning(f"Error de validación: {e}")
            return NarrationResponse(
                success=False,
                error=f"Error de validación: {e}",
                message="Corrige los datos de entrada y vuelve a intentarlo"
            )
            
        except Exception as e:
            logger.exception(f"Error inesperado en narración: {e}")
            return NarrationResponse(
                success=False,
                error=f"Error inesperado: {e}",
                message="Consulta los logs para más detalles"
            )
            
        finally:
            # No descargamos el motor: es un singleton que vive entre
            # narraciones en el mismo proceso. XttsEngine.unload() solo
            # hace gc.collect(), no descarga los pesos del modelo.
            pass
    
    # ---------------------------------------------------------------------------
    # Métodos auxiliares
    # ---------------------------------------------------------------------------
    
    def _create_engine(self) -> TTSEngine:
        """Crea y configura el motor TTS."""
        if self.custom_engine:
            return self.custom_engine
        return XttsEngine(
            threads=self.settings.threads,
            offline=True
        )
    
    def _get_out_path(self, request: NarrationRequest) -> Path:
        """Determina el path de salida."""
        if request.out_path:
            return Path(request.out_path)
        
        # Generar nombre por defecto
        filename = f"{request.project_name}_ch{request.chapter_id}.wav"
        return self.export_dir / filename
    
    # ---------------------------------------------------------------------------
    # Métodos para CLI
    # ---------------------------------------------------------------------------
    
    def narrate_chapter(
        self,
        project_name: str,
        chapter_id: int,
        regen: bool = False,
        cancel_event: threading.Event | None = None,
    ) -> NarrationResponse:
        """Narra un capítulo de un proyecto.
        
        Este método es conveniente para usar desde CLI.
        
        Args:
            project_name: Nombre del proyecto.
            chapter_id: ID del capítulo.
            regen: Si True, regenera todos los fragmentos.
            cancel_event: Evento para cancelación.
        
        Returns:
            NarrationResponse con el resultado.
        """
        # Obtener texto del capítulo (simplificado - en la práctica usar projects.py)
        from ..projects import get_chapter, ChapterNotFound
        
        try:
            chapter = get_chapter(self.data_dir / "voxforge.db", chapter_id)
            if chapter is None:
                return NarrationResponse(
                    success=False,
                    error=f"Capítulo {chapter_id} no encontrado"
                )
            
            # Obtener perfil del proyecto
            from ..projects import get_project, ProjectNotFound
            try:
                project = get_project(self.data_dir / "voxforge.db", project_name)
                voice_profile_name = project["voice_profile"]
                language = project.get("language", None)
                project_id = project.get("id", None)
            except ProjectNotFound:
                return NarrationResponse(
                    success=False,
                    error=f"Proyecto {project_name} no encontrado"
                )
            
            request = NarrationRequest(
                project_name=project_name,
                chapter_id=chapter_id,
                text=chapter["text"],
                voice_profile_name=voice_profile_name,
                language=language,
                regen=regen,
                cancel_event=cancel_event,
                project_id=project_id,
                resume=True,
            )
            
            return self.narrate(request)
            
        except ChapterNotFound:
            return NarrationResponse(
                success=False,
                error=f"Capítulo {chapter_id} no encontrado en el proyecto {project_name}"
            )
        except Exception as e:
            logger.exception(f"Error al narrar capítulo: {e}")
            return NarrationResponse(
                success=False,
                error=str(e)
            )
