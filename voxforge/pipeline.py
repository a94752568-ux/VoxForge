"""Narración: texto -> fragmentos -> audio (con caché y control de calidad) -> un único WAV.

Soporta reanudación de narraciones interrumpidas mediante el seguimiento de progreso
en la base de datos."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf

from .config import Settings
from .db import Store
from .engines.base import TTSEngine
from .textutil import split_segments
from .thermal import cpu_temp_c, wait_if_hot
from .audio_optimizer import (
    prepare_audio_for_cache,
    assemble_final_audio,
    analyze_fragment_quality,
)
from .utils import (
    SynthCancelledError, check_disk_space, estimate_audio_size_bytes,
    AudioValidationError, validate_audio_file,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    """Retorna la fecha actual en formato ISO."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

MIN_CHARS_FOR_QUALITY_CHECK = 40  # en textos muy cortos la velocidad de habla no es fiable
TARGET_CPS = 10.0                 # velocidad "típica" medida; sirve para elegir el mejor intento


@dataclass
class NarrationResult:
    out_path: Path
    fragments: int
    generated: int
    cached: int
    retried: int      # fragmentos que necesitaron más de un intento
    doubtful: int     # fragmentos que siguen anómalos tras agotar los reintentos
    audio_s: float
    compute_s: float
    waited_s: float
    pauses: int = 0   # pausas explícitas insertadas en el reensamblado


def _normalizar_texto(text: str) -> str:
    """Normaliza texto para la clave de caché: lowercase y colapsa espacios."""
    return " ".join(text.lower().split())


def fragment_hash(
    engine_name: str,
    ref_sha256: str,
    language: str,
    text: str,
    model_version: str | None = None,
    params: dict | None = None,
) -> str:
    """Identifica un fragmento con clave completa.

    La clave incluye: motor, muestra de referencia (sha256), idioma, texto
    normalizado, versión del modelo y todos los parámetros de generación que
    afectan el audio. Si cambia cualquiera, se regenera en lugar de servir
    audio obsoleto.
    """
    key = "\x1f".join(
        [
            engine_name,
            ref_sha256,
            language,
            _normalizar_texto(text),
            model_version or "",
            json.dumps(params or {}, sort_keys=True),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def speech_rate_ok(text: str, audio_s: float, settings: Settings) -> bool:
    """¿La duración del audio es razonable para la longitud del texto?"""
    if len(text) < MIN_CHARS_FOR_QUALITY_CHECK:
        return True
    if audio_s <= 0:
        return False
    cps = len(text) / audio_s
    # tolerancias amplias: demasiado rápido o demasiado lento
    return settings.min_cps <= cps <= settings.max_cps


def _best_attempt(attempts: list[tuple[np.ndarray, float, float]]) -> tuple[np.ndarray, float]:
    """Elige el intento cuya velocidad de habla esté más cerca de TARGET_CPS."""
    if not attempts:
        raise ValueError("no attempts")
    def score(item: tuple[np.ndarray, float, float]) -> float:
        audio, duration, cps = item
        return abs(cps - TARGET_CPS)
    best = min(attempts, key=score)
    return best[0], best[1]


def narrate(
    engine: TTSEngine,
    store: Store,
    settings: Settings,
    text: str,
    ref_wav: Path,
    language: str,
    out_path: Path,
    progress_cb: Callable[[int, int, str], None] | None = None,
    cancel_event: threading.Event | None = None,
    job_id: str | None = None,
    resume: bool = True,
) -> NarrationResult:
    """Pipeline principal: divide texto, sintetiza (o reutiliza caché), ensambla.

    Si resume=True y existe progreso previo en la BD para este job_id, continúa
    desde el último fragmento completado.
    """
    t0 = time.perf_counter()
    waited_total = 0.0
    compute_total = 0.0
    generated = 0
    cached = 0
    retried = 0
    doubtful = 0
    pause_total = 0

    segments = split_segments(text, settings.max_chars)
    n = len(segments)
    if n == 0:
        raise ValueError("texto vacío")

    # Cargar latentes de referencia una sola vez
    ref_sha = store.file_sha256(ref_wav)
    model_version = getattr(engine, "MODEL", None) or getattr(engine, "model_name", None)

    # --- FIX UnboundLocalError: inicializar ANTES del try ---
    text_index = 0
    fragments_processed = 0

    try:
        engine.load()
        latents = engine.get_latents(str(ref_wav))
    except Exception as e:
        logger.exception("fallo al cargar motor o latentes: %s", e)
        raise

    # Parámetros que afectan el audio (para la clave de caché)
    synth_params = {
        "temperature": getattr(settings, "temperature", 0.75),
        "top_p": getattr(settings, "top_p", 0.85),
        "top_k": getattr(settings, "top_k", 50),
        "repetition_penalty": getattr(settings, "repetition_penalty", 5.0),
        "length_penalty": getattr(settings, "length_penalty", 1.0),
        "speed": getattr(settings, "speed", 1.0),
    }

    # Reanudación
    start_idx = 0
    if resume and job_id:
        prog = store.get_progress(job_id)
        if prog and prog.get("ref_sha") == ref_sha:
            start_idx = int(prog.get("text_index", 0))
            fragments_processed = int(prog.get("fragments_processed", 0))
            logger.info("reanudando desde fragmento %s", start_idx)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="voxforge_"))
    fragment_paths: list[Path] = []

    try:
        for i, seg in enumerate(segments):
            if cancel_event and cancel_event.is_set():
                raise SynthCancelledError("cancelado por el usuario")

            if i < start_idx:
                # ya procesado en una ejecución anterior; recuperar del caché si es posible
                h = fragment_hash(
                    engine.name, ref_sha, language, seg,
                    model_version=model_version, params=synth_params,
                )
                cached_path = store.cache_get(h)
                if cached_path and cached_path.exists():
                    fragment_paths.append(cached_path)
                    cached += 1
                    text_index = i + 1
                    fragments_processed += 1
                    if progress_cb:
                        progress_cb(i + 1, n, "reanudado (caché)")
                    continue
                # si no está en caché, regeneramos
                start_idx = i  # forzar regeneración desde aquí

            if progress_cb:
                progress_cb(i, n, f"sintetizando {i+1}/{n}")

            # Control térmico
            waited = wait_if_hot(settings)
            waited_total += waited

            h = fragment_hash(
                engine.name, ref_sha, language, seg,
                model_version=model_version, params=synth_params,
            )
            cached_path = store.cache_get(h)
            if cached_path and cached_path.exists():
                fragment_paths.append(cached_path)
                cached += 1
                text_index = i + 1
                fragments_processed += 1
                if progress_cb:
                    progress_cb(i + 1, n, "caché")
                continue

            # Espacio en disco
            est = estimate_audio_size_bytes(len(seg), settings.sample_rate)
            check_disk_space(tmp_dir, est * 2)

            attempts: list[tuple[np.ndarray, float, float]] = []
            max_retries = max(1, getattr(settings, "max_retries", 2))
            last_err: Exception | None = None

            for attempt in range(max_retries):
                if cancel_event and cancel_event.is_set():
                    raise SynthCancelledError("cancelado por el usuario")
                t_synth = time.perf_counter()
                try:
                    audio = engine.synthesize(
                        text=seg,
                        speaker_wav=str(ref_wav),
                        language=language,
                        latents=latents,
                        **{k: v for k, v in synth_params.items() if hasattr(engine, "supports") or True},
                    )
                    # audio puede ser (np.ndarray, sr) o solo ndarray
                    if isinstance(audio, tuple):
                        wav, sr = audio
                    else:
                        wav = audio
                        sr = settings.sample_rate
                    duration = len(wav) / float(sr)
                    cps = len(seg) / duration if duration > 0 else 0.0
                    attempts.append((wav, duration, cps))
                    compute_total += time.perf_counter() - t_synth

                    if speech_rate_ok(seg, duration, settings):
                        break
                    retried += 1
                    logger.warning(
                        "velocidad anómala (cps=%.1f) en fragmento %s intento %s; reintentando",
                        cps, i, attempt + 1,
                    )
                except Exception as e:
                    last_err = e
                    logger.warning("error síntesis fragmento %s intento %s: %s", i, attempt + 1, e)
                    compute_total += time.perf_counter() - t_synth

            if not attempts:
                raise RuntimeError(f"falló síntesis del fragmento {i}: {last_err}") from last_err

            wav, duration = _best_attempt(attempts)
            if not speech_rate_ok(seg, duration, settings):
                doubtful += 1
                logger.warning("fragmento %s sigue dudoso tras reintentos (cps anómala)", i)

            # Normalizar / preparar para caché
            wav = prepare_audio_for_cache(wav, settings.sample_rate, settings)

            frag_path = tmp_dir / f"frag_{i:05d}.wav"
            sf.write(str(frag_path), wav, settings.sample_rate)
            validate_audio_file(frag_path)

            # Guardar en caché
            store.cache_put(h, frag_path)
            fragment_paths.append(frag_path)
            generated += 1
            text_index = i + 1
            fragments_processed += 1

            if job_id:
                store.set_progress(job_id, {
                    "text_index": text_index,
                    "fragments_processed": fragments_processed,
                    "ref_sha": ref_sha,
                    "updated": _now(),
                })

            if progress_cb:
                progress_cb(i + 1, n, "generado")

        # Ensamblar
        if progress_cb:
            progress_cb(n, n, "ensamblando")

        final_audio, pause_total = assemble_final_audio(
            fragment_paths, settings.sample_rate, settings
        )
        sf.write(str(out_path), final_audio, settings.sample_rate)
        validate_audio_file(out_path)

        if job_id:
            store.clear_progress(job_id)

    finally:
        # limpiar temporales que no estén en caché
        for p in list(tmp_dir.glob("*.wav")):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

    audio_s = len(final_audio) / float(settings.sample_rate) if "final_audio" in dir() else 0.0
    # recalcular duración real
    try:
        info = sf.info(str(out_path))
        audio_s = info.duration
    except Exception:
        pass

    return NarrationResult(
        out_path,
        n,
        generated,
        cached,
        retried,
        doubtful,
        audio_s,
        compute_total,
        waited_total,
        pause_total,
    )
