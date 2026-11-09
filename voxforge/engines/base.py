from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np


class ModelUnavailableError(RuntimeError):
    """El modelo no se pudo cargar (p. ej. aún no está descargado y no hay conexión)."""


class TTSEngine(ABC):
    """Interfaz común: añadir un motor nuevo no obliga a tocar el resto de la aplicación."""

    name: str
    sample_rate: int

    @abstractmethod
    def load(self) -> None:
        """Carga el modelo en memoria."""

    @abstractmethod
    def unload(self) -> None:
        """Libera el modelo de memoria."""

    @abstractmethod
    def synthesize(self, text: str, reference_wav: Path, language: str, seed: int) -> np.ndarray:
        """Devuelve audio mono float32 a self.sample_rate, clonando la voz de reference_wav."""

    def speaker_embedding(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Huella de voz del audio (opcional). Los motores que la ofrezcan permiten comparar voces."""
        raise NotImplementedError(f"El motor {self.name} no ofrece comparación de voces.")
