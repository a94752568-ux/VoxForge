"""Servicio de gestión de proyectos."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..db import Store
from ..config import Settings
from ..utils import ValidationError

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


# =============================================================================
# DTOs
# =============================================================================

@dataclass
class ProjectRequest:
    """Solicitud para crear un proyecto."""
    name: str
    voice_profile: str
    language: str | None = None


@dataclass
class ChapterRequest:
    """Solicitud para crear un capítulo."""
    project_name: str
    title: str
    text: str | None = None
    file_path: Path | None = None


@dataclass
class ProjectResponse:
    """Respuesta de una operación con proyectos."""
    success: bool
    project_id: int | None = None
    chapter_id: int | None = None
    error: str | None = None
    message: str = ""


# =============================================================================
# Servicio de Gestión de Proyectos
# =============================================================================

class ProjectService:
    """Servicio de gestión de proyectos y capítulos.
    
    Centraliza toda la lógica relacionada con:
    - Creación, listado y eliminación de proyectos
    - Gestión de capítulos
    - Progreso de narración
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
        self.db_path = self.data_dir / "voxforge.db"
        
        logger.debug(f"ProjectService inicializado: db_path={self.db_path}")
    
    # ---------------------------------------------------------------------------
    # Validaciones
    # ---------------------------------------------------------------------------
    
    def _validate_project_name(self, name: str) -> None:
        """Valida el nombre de un proyecto."""
        if not name or len(name) > 100:
            raise ValidationError("El nombre del proyecto debe tener entre 1 y 100 caracteres")
        
        if not name.replace("_", "").replace("-", "").replace(" ", "").isalnum():
            raise ValidationError(
                "El nombre solo puede contener caracteres alfanuméricos, espacios, guiones y guiones bajos"
            )
    
    def _validate_voice_profile(self, profile_name: str) -> None:
        """Valida que el perfil de voz exista."""
        profile = self.store.get_profile(profile_name)
        if not profile:
            raise ValidationError(
                f"Perfil de voz '{profile_name}' no encontrado. "
                "Crea el perfil primero con: voxforge voice add"
            )
    
    # ---------------------------------------------------------------------------
    # Operaciones de proyectos
    # ---------------------------------------------------------------------------
    
    def create_project(self, request: ProjectRequest) -> ProjectResponse:
        """Crea un nuevo proyecto.
        
        Args:
            request: Solicitud de creación de proyecto.
        
        Returns:
            ProjectResponse con el resultado.
        """
        try:
            # Validar entradas
            self._validate_project_name(request.name)
            self._validate_voice_profile(request.voice_profile)
            
            # Verificar que no exista ya
            from ..projects import get_project, ProjectNotFound
            try:
                get_project(self.db_path, request.name)
                return ProjectResponse(
                    success=False,
                    error=f"Ya existe un proyecto con el nombre '{request.name}'"
                )
            except ProjectNotFound:
                pass  # No existe, podemos crear
            
            # Crear el proyecto
            from ..projects import create_project
            project_id = create_project(
                self.db_path,
                request.name,
                request.voice_profile,
                language=request.language
            )
            
            logger.info(f"Proyecto creado: {request.name} (id={project_id})")
            
            return ProjectResponse(
                success=True,
                project_id=project_id,
                message=f"Proyecto '{request.name}' creado correctamente"
            )
            
        except ValidationError as e:
            logger.warning(f"Error de validación al crear proyecto: {e}")
            return ProjectResponse(
                success=False,
                error=str(e)
            )
            
        except Exception as e:
            logger.exception(f"Error al crear proyecto: {e}")
            return ProjectResponse(
                success=False,
                error=f"Error inesperado: {e}"
            )
    
    def get_project(self, name: str) -> dict | None:
        """Obtiene un proyecto por nombre."""
        from ..projects import get_project, ProjectNotFound
        try:
            return get_project(self.db_path, name)
        except ProjectNotFound:
            return None
    
    def list_projects(self) -> list[dict]:
        """Lista todos los proyectos."""
        from ..projects import list_projects
        return list_projects(self.db_path)
    
    def delete_project(self, name: str, force: bool = False) -> ProjectResponse:
        """Elimina un proyecto.
        
        Args:
            name: Nombre del proyecto a eliminar.
            force: Si True, elimina aunque tenga capítulos.
        
        Returns:
            ProjectResponse con el resultado.
        """
        try:
            from ..projects import delete_project, ProjectNotFound, ProjectError
            
            try:
                delete_project(self.db_path, name, yes=force)
                logger.info(f"Proyecto eliminado: {name}")
                return ProjectResponse(
                    success=True,
                    message=f"Proyecto '{name}' eliminado correctamente"
                )
            except ProjectNotFound:
                return ProjectResponse(
                    success=False,
                    error=f"Proyecto '{name}' no encontrado"
                )
            except ProjectError as e:
                return ProjectResponse(
                    success=False,
                    error=f"Error al eliminar proyecto: {e}"
                )
                
        except Exception as e:
            logger.exception(f"Error al eliminar proyecto: {e}")
            return ProjectResponse(
                success=False,
                error=f"Error inesperado: {e}"
            )
    
    # ---------------------------------------------------------------------------
    # Operaciones de capítulos
    # ---------------------------------------------------------------------------
    
    def add_chapter(self, request: ChapterRequest) -> ProjectResponse:
        """Añade un capítulo a un proyecto.
        
        Args:
            request: Solicitud de creación de capítulo.
        
        Returns:
            ProjectResponse con el resultado.
        """
        try:
            # Validar proyecto
            project = self.get_project(request.project_name)
            if not project:
                return ProjectResponse(
                    success=False,
                    error=f"Proyecto '{request.project_name}' no encontrado"
                )
            
            # Validar que el proyecto existe
            from ..projects import add_chapter
            chapter_id = add_chapter(
                self.db_path,
                request.project_name,
                request.title,
                text=request.text,
                file=request.file_path
            )
            
            logger.info(
                f"Capítulo añadido: {request.title} "
                f"(proyecto={request.project_name}, id={chapter_id})"
            )
            
            return ProjectResponse(
                success=True,
                chapter_id=chapter_id,
                message=f"Capítulo '{request.title}' añadido al proyecto '{request.project_name}'"
            )
            
        except Exception as e:
            logger.exception(f"Error al añadir capítulo: {e}")
            return ProjectResponse(
                success=False,
                error=f"Error al añadir capítulo: {e}"
            )
    
    def get_chapter(self, project_name: str, chapter_id: int) -> dict | None:
        """Obtiene un capítulo de un proyecto."""
        from ..projects import get_chapter, ChapterNotFound
        try:
            return get_chapter(self.db_path, chapter_id)
        except ChapterNotFound:
            return None
    
    def list_chapters(self, project_name: str) -> list[dict]:
        """Lista todos los capítulos de un proyecto."""
        from ..projects import list_chapters
        return list_chapters(self.db_path, project_name)
    
    def get_project_progress(self, project_name: str, chapter_id: int) -> dict | None:
        """Obtiene el progreso de narración de un capítulo."""
        # Esto requerirá implementación en db.py
        try:
            return self.store.get_project_progress(project_name, chapter_id)
        except Exception:
            return None
