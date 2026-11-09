"""Capa de servicios de VoxForge Local.

Esta capa centraliza la lógica de negocio, separándola de la interfaz de usuario
(CLI y GUI). Esto permite:
- Evitar duplicación de código entre CLI y GUI
- Facilitar el testing
- Mejorar la mantenibilidad
- Proporcionar una API consistente
"""

from .narrator import (
    NarratorService,
    NarrationRequest,
    NarrationResponse,
    NarrationResult,
)
from .voice_manager import (
    VoiceManagerService,
    VoiceProfileRequest,
    VoiceProfileResponse,
)
from .project_service import (
    ProjectService,
    ProjectRequest,
    ChapterRequest,
    ProjectResponse,
)

__all__ = [
    # Narrator Service
    "NarratorService",
    "NarrationRequest",
    "NarrationResponse",
    "NarrationResult",
    # Voice Manager Service
    "VoiceManagerService",
    "VoiceProfileRequest",
    "VoiceProfileResponse",
    # Project Service
    "ProjectService",
    "ProjectRequest",
    "ChapterRequest",
    "ProjectResponse",
]
