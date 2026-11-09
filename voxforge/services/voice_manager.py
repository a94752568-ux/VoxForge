"""Servicio de gestión de perfiles de voz."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..db import Store
from ..config import Settings
from ..utils import ValidationError, sanitize_path

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


# =============================================================================
# DTOs
# =============================================================================

@dataclass
class VoiceProfileRequest:
    """Solicitud para crear un perfil de voz."""
    name: str
    reference_path: Path
    language: str


@dataclass
class VoiceProfileResponse:
    """Respuesta de una operación con perfiles de voz."""
    success: bool
    profile_id: int | None = None
    error: str | None = None
    message: str = ""


# =============================================================================
# Servicio de Gestión de Voces
# =============================================================================

class VoiceManagerService:
    """Servicio de gestión de perfiles de voz.
    
    Centraliza toda la lógica relacionada con:
    - Creación de perfiles de voz
    - Validación de muestras de referencia
    - Listado y eliminación de perfiles
    """
    
    def __init__(
        self,
        store: Store,
        settings: Settings,
        data_dir: Path,
    ):
        """Inicializa el servicio.
        
        Args:
            store: Store de SQLite.
            settings: Configuración de VoxForge.
            data_dir: Directorio base de datos.
        """
        self.store = store
        self.settings = settings
        self.data_dir = Path(data_dir)
        self.voices_dir = self.data_dir / "voices"
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"VoiceManagerService inicializado: voices_dir={self.voices_dir}")
    
    # ---------------------------------------------------------------------------
    # Validaciones
    # ---------------------------------------------------------------------------
    
    def _validate_profile_name(self, name: str) -> None:
        """Valida el nombre de un perfil."""
        if not name or len(name) > 60:
            raise ValidationError("El nombre debe tener entre 1 y 60 caracteres")
        
        if not name.replace("_", "").replace("-", "").isalnum():
            raise ValidationError(
                "El nombre solo puede contener caracteres alfanuméricos, guiones (-) y guiones bajos (_)"
            )
    
    def _validate_reference_path(self, path: Path) -> Path:
        """Valida el path de referencia."""
        resolved = sanitize_path(path)
        
        if not resolved.exists():
            raise ValidationError(f"El archivo de referencia no existe: {resolved}")
        
        if not resolved.is_file():
            raise ValidationError(f"El path no es un archivo: {resolved}")
        
        # Validar formato
        valid_extensions = {".wav", ".flac", ".mp3", ".ogg", ".oga"}
        if resolved.suffix.lower() not in valid_extensions:
            raise ValidationError(
                f"Formato no soportado: {resolved.suffix}. "
                f"Formatos válidos: {', '.join(valid_extensions)}"
            )
        
        return resolved
    
    def _validate_language(self, language: str) -> None:
        """Valida el código de idioma."""
        if not language or len(language) > 10:
            raise ValidationError("El código de idioma debe tener entre 1 y 10 caracteres")
    
    # ---------------------------------------------------------------------------
    # Operaciones
    # ---------------------------------------------------------------------------
    
    def create_profile(self, request: VoiceProfileRequest) -> VoiceProfileResponse:
        """Crea un nuevo perfil de voz.
        
        Args:
            request: Solicitud de creación de perfil.
        
        Returns:
            VoiceProfileResponse con el resultado.
        """
        try:
            # Validar entradas
            self._validate_profile_name(request.name)
            reference_path = self._validate_reference_path(request.reference_path)
            self._validate_language(request.language)
            
            # Verificar que no exista ya
            existing = self.store.get_profile(request.name)
            if existing:
                return VoiceProfileResponse(
                    success=False,
                    error=f"Ya existe un perfil con el nombre '{request.name}'"
                )
            
            # Copiar el archivo de referencia a la carpeta de voces
            import hashlib
            ref_sha256 = hashlib.sha256(reference_path.read_bytes()).hexdigest()
            target_path = self.voices_dir / f"{request.name}_{ref_sha256[:8]}.wav"
            
            # Convertir a WAV mono 24kHz si es necesario
            from .. import cli
            error = cli._convert_to_wav24(reference_path, target_path)
            if error:
                return VoiceProfileResponse(
                    success=False,
                    error=f"Error al convertir el archivo de referencia: {error}"
                )
            
            # Guardar en la base de datos
            profile_id = self.store.add_profile(
                request.name,
                target_path,
                ref_sha256,
                request.language
            )
            
            logger.info(f"Perfil de voz creado: {request.name} (id={profile_id})")
            
            return VoiceProfileResponse(
                success=True,
                profile_id=profile_id,
                message=f"Perfil '{request.name}' creado correctamente"
            )
            
        except ValidationError as e:
            logger.warning(f"Error de validación al crear perfil: {e}")
            return VoiceProfileResponse(
                success=False,
                error=str(e)
            )
            
        except Exception as e:
            logger.exception(f"Error al crear perfil de voz: {e}")
            return VoiceProfileResponse(
                success=False,
                error=f"Error inesperado: {e}"
            )
    
    def get_profile(self, name: str) -> sqlite3.Row | None:
        """Obtiene un perfil de voz por nombre."""
        return self.store.get_profile(name)
    
    def list_profiles(self) -> list[sqlite3.Row]:
        """Lista todos los perfiles de voz."""
        return self.store.list_profiles()
    
    def delete_profile(self, name: str) -> VoiceProfileResponse:
        """Elimina un perfil de voz.
        
        Args:
            name: Nombre del perfil a eliminar.
        
        Returns:
            VoiceProfileResponse con el resultado.
        """
        try:
            profile = self.store.get_profile(name)
            if not profile:
                return VoiceProfileResponse(
                    success=False,
                    error=f"Perfil '{name}' no encontrado"
                )
            
            # Eliminar el archivo de referencia
            ref_path = Path(profile["ref_path"])
            if ref_path.exists():
                ref_path.unlink()
            
            # Eliminar de la base de datos
            # NOTE: Esto requiere implementar delete_profile en Store
            # Por ahora, usamos SQL directo
            with self.store.conn:
                self.store.conn.execute(
                    "DELETE FROM voice_profiles WHERE name = ?",
                    (name,)
                )
            
            logger.info(f"Perfil de voz eliminado: {name}")
            
            return VoiceProfileResponse(
                success=True,
                message=f"Perfil '{name}' eliminado correctamente"
            )
            
        except Exception as e:
            logger.exception(f"Error al eliminar perfil: {e}")
            return VoiceProfileResponse(
                success=False,
                error=f"Error al eliminar perfil: {e}"
            )
