from __future__ import annotations

import gc
import os
from pathlib import Path

import numpy as np

from .base import ModelUnavailableError, TTSEngine
from ..audio_optimizer import optimize_fragment


class XttsEngine(TTSEngine):
    """Coqui XTTS-v2 (paquete coqui-tts) ejecutado en CPU.

    Implementa singleton a nivel de módulo: la primera instancia carga el
    modelo y las siguientes lo reusan. Esto evita pagar 12s de carga por cada
    fragmento/capítulo cuando varios jobs se ejecutan en el mismo proceso.
    """

    name = "xtts-v2"
    sample_rate = 24000
    MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

    _instance: "XttsEngine | None" = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, threads: int = 2, offline: bool = True):
        # __init__ se llama en cada instancia (incluso si es singleton), así que
        # solo inicializamos una vez para no sobrescribir hilos ya fijados.
        if XttsEngine._initialized:
            return
        self.threads = threads
        self.offline = offline  # True: nunca se contacta con Internet (modo normal)
        self._tts = None
        self._latentes_cache: dict = {}
        XttsEngine._initialized = True

    def load(self) -> None:
        # Si el modelo ya está cargado (singleton reusado), no recargar.
        if self._tts is not None:
            return

        # Debe hacerse antes de importar torch/TTS: las librerías leen estas variables al importarse.
        for var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
            if self.offline:
                os.environ[var] = "1"
            else:
                os.environ.pop(var, None)
        try:
            import torch
            from TTS.api import TTS
        except ImportError as exc:
            raise ModelUnavailableError(
                "Faltan torch o coqui-tts. ¿Ac
tivaste el entorno? Ejecuta: source ~/VoxForge/.venv/bin/activate"
            ) from exc

        try:  # avisos de configuración de transformers sin efecto en el audio
            from transformers.utils import logging as hf_logging
            hf_logging.set_verbosity_error()
        except Exception:
            pass
        # Configurar hilos antes de crear pools de torch (orden importa:
        # interop primero, luego intraop). Se envuelven en try/except porque
        # quien llama al engine (bench o GUI) puede haberlos fijado ya.
        try:
            torch.set_num_interop_threads(1)
        except (RuntimeError, AttributeError):
            # AttributeError: builds de torch (p.ej. Python 3.14) sin esta API
            pass
        try:
            torch.set_num_threads(self.threads)
        except RuntimeError:
            pass
        try:
            self._tts = TTS(self.MODEL)  # CPU por defecto
        except Exception as exc:
            if not self.offline:
                raise
            raise ModelUnavailableError(
                "No se pudo cargar XTTS-v2 sin conexión. Si es la primera vez, descarga el modelo "
                f"con: python -m voxforge model download  ({type(exc).__name__}: {exc})"
            ) from exc
        # Ganancia gratis y sin riesgo: modo evaluación desactiva dropout y acelera inferencia
        self._tts.synthesizer.tts_model.eval()

    def unload(self) -> None:
        # El motor es un singleton: no lo descargamos realmente para que
        # permanezca cargado entre narraciones en el mismo proceso.
        # gc.collect() libera memoria sin descartar los pesos del modelo.
        gc.collect()

    def synthesize(
        self,
        text: str,
        reference_wav: Path | None = None,
        language: str = "es",
        seed: int = 0,
        latentes: tuple | None = None,
        write_to: Path | None = None,
        **generation_params,
    ) -> np.ndarray:
        import torch

        if self._tts is None:
            raise RuntimeError("El modelo no está cargado: llama a load() primero.")
        
model = self._tts.synthesizer.tts_model
        torch.manual_seed(seed)  # misma entrada + misma semilla = mismo audio

        # Obtener latentes: usar los pasados o calcular/usar caché del speaker_wav
        if latentes is None:
            if reference_wav is None:
                raise ValueError("reference_wav es obligatorio si no se pasan latentes")
            latentes = self.get_latents(reference_wav, use_cache=True)
        gpt_cond_latent, speaker_embedding = latentes

        wav = model.inference(
            text=text,
            gpt_cond_latent=gpt_cond_latent,
            speaker_embedding=speaker_embedding,
            language=language,
            **generation_params,
        )
        # Coqui puede devolver np.ndarray directamente o un dict con la clave 'wav'
        if isinstance(wav, dict):
            wav = wav.get("wav", wav.get("audio", list(wav.values())[0]))
        wav = np.asarray(wav, dtype=np.float32)

        # --- Post-procesamiento profesional para reducir anomalías ---
        # Aplica: DC offset removal, fade in/out, normalización RMS y soft-clip.
        # Esto elimina clicks, iguala volumen y previene distorsión antes de
        # que el audio salga del motor.
        try:
            wav = optimize_fragment(
                wav,
                self.sample_rate,
                target_rms=0.15,
                fade_ms=5.0,
                trim_edges=False,  # no recortar en el motor; el pipeline lo hace
                remove_dc=True,
                soft_limit=True,
                normalize=True,
            )
        except Exception:
            # Si la optimización falla, devolver el audio crudo sin bloquear
            pass
        # ------------------------------------------------------------

        # Escritura a disco separada de la síntesis pura
        if write_to is not None:
            import soundfile as sf
            sf.write(str(write_to), wav, self.sample_rate)

        return wav

    def get_latents(self,
 speaker_wav: Path, use_cache: bool = True) -> tuple:
        """Devuelve (gpt_cond_latent, speaker_embedding) para el speaker dado.

        Si use_cache y ya se calcularon para este wav, devuelve el cache.
        """
        import hashlib

        h = hashlib.sha256(Path(speaker_wav).read_bytes()).hexdigest()
        if use_cache and h in self._latentes_cache:
            return self._latentes_cache[h]

        model = self._tts.synthesizer.tts_model
        latents = model.get_conditioning_latents(audio_path=str(speaker_wav))
        # Coqui devuelve (gpt_cond_latent, speaker_embedding) o un tuple de 2
        if isinstance(latents, tuple) and len(latents) == 2:
            gpt_cond_latent, speaker_embedding = latents
        else:
            # Alguna versión devuelve dict o objeto; intentamos adaptar
            raise ModelUnavailableError(
                f"Formato inesperado de get_conditioning_latents: {type(latents)}"
            )

        self._latentes_cache[h] = (gpt_cond_latent, speaker_embedding)
        return gpt_cond_latent, speaker_embedding

    def speaker_embedding(self, audio: np.ndarray, sr: int) -> np.ndarray:
        import torch

        if self._tts is None:
            raise RuntimeError("El modelo no está cargado: llama a load() primero.")
        try:
            model = self._tts.synthesizer.tts_model
            wav = torch.from_numpy(np.asarray(audio, dtype=np.float32)).unsqueeze(0)
            with torch.no_grad():
                emb = model.get_speaker_embedding(wav, sr)
        except AttributeError as exc:
            raise ModelUnavailableError(
                "Esta versión de coqui-tts no expone el codificador de hablante "
                f"({exc}). Avísame con este mensaje para adaptarlo."
            ) from exc
        return emb.detach().cpu().numpy().reshape(-1)
