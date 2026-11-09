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
    return settings.rate_min_cps <= len(text) / audio_s <= settings.rate_max_cps


def _distance_to_typical(text: str, audio_s: float) -> float:
    return abs(len(text) / audio_s - TARGET_CPS) if audio_s > 0 else float("inf")


def _export_audio(audio: np.ndarray, sr: int, out_path: Path) -> None:
    """Escribe el audio a out_path, convirtiendo con ffmpeg si la extensión no es WAV."""
    ext = out_path.suffix.lower()

    if ext == ".wav":
        sf.write(out_path, audio, sr, subtype="PCM_16")
        return

    if ext not in (".flac", ".mp3", ".ogg"):
        raise ValueError(
            f"Formato de exportación no soportado: {ext}. "
            "Usa .wav, .flac, .mp3 o .ogg"
        )

    # Escribimos un WAV temporal y convertimos con ffmpeg.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        sf.write(tmp_path, audio, sr, subtype="PCM_16")

        if ext == ".flac":
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp_path),
                   "-c:a", "flac", str(out_path)]
        elif ext == ".mp3":
            # Calidad VBR ~190 kbps (equivalente a -q:a 2)
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp_path),
                   "-c:a", "libmp3lame", "-q:a", "2", str(out_path)]
        else:  # .ogg
            # Calidad VBR ~160 kbps (equivalente a -q:a 5)
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp_path),
                   "-c:a", "libvorbis", "-q:a", "5", str(out_path)]

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg fallo al exportar a {ext}:\n{e.stderr}") from e
    finally:
        tmp_path.unlink(missing_ok=True)


def narrate(
    text: str,
    profile,  # fila de voice_profiles
    engine: TTSEngine,
    store: Store,
    settings: Settings,
    cache_dir: Path,
    out_path: Path,
    language: str | None = None,
    regen: bool = False,
    regen_fragment: int | None = None,  # 1-based: fuerza la regeneración de un fragmento de texto
    regen_seed: int | None = None,      # semilla fija para reproducir el take regenerado
    log: Callable[[str], None] = print,
    project_name: str | None = None,   # Nombre del proyecto para reanudación
    chapter_id: int | None = None,      # ID del capítulo para reanudación
    resume: bool = True,               # Intentar reanudar desde progreso guardado
    cancel_event: threading.Event | None = None,  # Evento para cancelación
) -> NarrationResult:
    """Narra texto a audio con soporte para reanudación.
    
    Args:
        text: Texto a narrar.
        profile: Fila de voice_profiles con la voz de referencia.
        engine: Motor TTS a usar.
        store: Store de SQLite para caché y progreso.
        settings: Configuración de VoxForge.
        cache_dir: Directorio de caché.
        out_path: Path de salida del audio.
        language: Idioma (si None, usa el del perfil).
        regen: Si True, regenera todos los fragmentos.
        regen_fragment: Fuerza regeneración de un fragmento específico (1-based).
        regen_seed: Semilla fija para regeneración reproducible.
        log: Función de logging.
        project_name: Nombre del proyecto (para guardar progreso).
        chapter_id: ID del capítulo (para guardar progreso).
        resume: Si True, intenta reanudar desde el progreso guardado.
        cancel_event: Evento threading.Event para cancelación.
    
    Returns:
        NarrationResult con estadísticas de la narración.
    
    Raises:
        ValueError: Si el texto está vacío.
        SynthCancelledError: Si se solicita cancelación.
    """
    # Validar que haya texto
    if not text or not text.strip():
        raise ValueError("El texto está vacío.")
    
    language = language or profile["language"]
    
    # Dividir en segmentos
    segments = split_segments(text, settings.max_chunk_chars)

    text_total = sum(1 for seg in segments if seg.kind == "text")
    pause_total = len(segments) - text_total

    if text_total == 0 and pause_total == 0:
        raise ValueError("El texto está vacío.")

    if regen_fragment is not None and (regen_fragment < 1 or regen_fragment > text_total):
        raise ValueError(f"Fragmento {regen_fragment} fuera de rango (1-{text_total}).")
    
    # Verificar cancelación al inicio
    if cancel_event and cancel_event.is_set():
        raise SynthCancelledError("Narración cancelada antes de empezar")
    
    # Validar espacio en disco si tenemos project_name
    if project_name and chapter_id is not None:
        estimated_size = estimate_audio_size_bytes(
            len(text),
            sample_rate=engine.sample_rate,
            cps=settings.rate_min_cps
        )
        try:
            check_disk_space(out_path, estimated_size * 2)  # 2x para margen
        except Exception as e:
            logger.error(f"Error de espacio en disco: {e}")
            raise
    
    # Intentar reanudar desde progreso guardado
    start_fragment = 0
    if resume and project_name and chapter_id is not None:
        progress = store.get_project_progress(project_name, chapter_id)
        if progress and progress["status"] in ("running", "paused"):
            start_fragment = progress["current_fragment"]
            logger.info(
                f"Reanudando narración desde fragmento {start_fragment} "
                f"(proyecto={project_name}, capítulo={chapter_id})"
            )
            log(f"Reanudando desde fragmento {start_fragment}...")
        else:
            # Iniciar nuevo progreso
            store.update_project_progress(
                project_name, chapter_id,
                total_fragments=text_total,
                processed_fragments=0,
                current_fragment=0,
                status="running"
            )
    else:
        # Iniciar nuevo progreso si tenemos project_name
        if project_name and chapter_id is not None:
            store.update_project_progress(
                project_name, chapter_id,
                total_fragments=text_total,
                processed_fragments=0,
                current_fragment=0,
                status="running"
            )

    sr = engine.sample_rate
    parts: list[np.ndarray] = []
    generated = cached = retried = doubtful = 0
    compute_total = waited_total = 0.0
    loaded = False

    if pause_total:
        log(
            f"{text_total} fragmentos, {pause_total} pausas explícitas, "
            f"idioma '{language}', voz '{profile['name']}'"
        )
    else:
        log(f"{text_total} fragmentos, idioma '{language}', voz '{profile['name']}'")

    try:
        # Cargar el modelo una vez (idempotente si el singleton ya lo cargó)
        engine.load()
        # Obtener latentes del speaker una vez (caché si es el mismo speaker)
        # Se hace antes del bucle para que todos los fragmentos del mismo
        # speaker reusen los latentes pre-computados.
        latentes = engine.get_latents(Path(profile["ref_path"]))

        text_index = 0
        fragments_processed = 0

        for seg_pos, seg in enumerate(segments):
            # Verificar cancelación al inicio de cada segmento
            if cancel_event and cancel_event.is_set():
                raise SynthCancelledError("Narración cancelada por el usuario")

            # Saltar fragmentos ya procesados (reanudación)
            if seg.kind == "text" and text_index < start_fragment:
                text_index += 1
                fragments_processed += 1
                continue

            if seg.kind == "pause":
                if seg.seconds > 0:
                    parts.append(np.zeros(int(sr * seg.seconds), dtype=np.float32))
                continue

            text_index += 1
            chunk_text = seg.text
            paragraph_end = seg.paragraph_end

            digest = fragment_hash(
                engine.name,
                profile["ref_sha256"],
                language,
                chunk_text,
                model_version=engine.MODEL,
                params={},
            )
            row = store.get_fragment(digest)
            cache_file = cache_dir / f"{digest}.wav"
            usable = row is not None and cache_file.exists()

            force_regen_one = regen_fragment is not None and text_index == regen_fragment

            # ¿hay que (re)generar? Sí si no hay caché, si se pide --regen, si se fuerza un
            # fragmento individual, o si el guardado como bueno tiene duración anómala.
            needs = (not usable) or regen or force_regen_one or (
                row is not None and row["ok"] == 1 and not speech_rate_ok(chunk_text, row["audio_s"], settings)
            )

            if not needs:
                # Validar integridad del caché antes de usarlo
                try:
                    validate_audio_file(cache_file, require_non_silent=False)
                except AudioValidationError as exc:
                    log(f"  [{text_index}/{text_total}] caché corrupto, regenerando: {exc}")
                    needs = True
                else:
                    audio, _ = sf.read(cache_file, dtype="float32")
                    cached += 1
                    note = "" if row["ok"] else " (aviso: fragmento dudoso, usa --regen para reintentar)"
                    if not row["ok"]:
                        doubtful += 1
                    log(f"[{text_index}/{text_total}] en caché{note}")
            else:
                if settings.thermal_guard:
                    waited_total += wait_if_hot(settings.temp_pause_c, settings.temp_resume_c, log)
                if not loaded:
                    log("Cargando el modelo (solo la primera vez de esta ejecución)...")
                    engine.load()
                    loaded = True

                base_seed = int(digest[:8], 16)
                if force_regen_one:
                    if regen_seed is not None:
                        base_seed = regen_seed
                    else:
                        base_seed = int(time.time_ns()) & 0xFFFFFFFF
                    log(f"  semilla de regeneración: {base_seed}")

                first = (row["attempt"] + 1) if usable and not force_regen_one else 0
                best = None  # (audio, attempt, audio_s, good)
                spent = 0.0
                tries = 0

                for attempt in range(first, first + 1 + settings.max_retries):
                    t0 = time.time()
                    audio = engine.synthesize(
                        chunk_text,
                        language=language,
                        seed=base_seed + attempt,
                        latentes=latentes,
                    )
                    spent += time.time() - t0
                    tries += 1
                    audio_s = len(audio) / sr
                    good = speech_rate_ok(chunk_text, audio_s, settings)

                    if best is None or (good and not best[3]) or (
                        good == best[3]
                        and _distance_to_typical(chunk_text, audio_s)
                        < _distance_to_typical(chunk_text, best[2])
                    ):
                        best = (audio, attempt, audio_s, good)

                    if good:
                        break

                    log(
                        f"  duración anómala ({len(chunk_text) / max(audio_s, 1e-9):.1f} car/s), "
                        f"intento {attempt - first + 1}"
                    )

                audio, attempt, audio_s, good = best
                # --- Optimización profesional de audio por fragmento ---
                # Aplica: DC offset removal, trimming silencio, fade in/out,
                # normalización RMS y soft-clip para reducir anomalías.
                try:
                    audio = prepare_audio_for_cache(audio, sr, settings=settings)
                    # Recalcular duración tras optimización
                    audio_s = len(audio) / sr
                    # Análisis de calidad: detectar anomalías residuales
                    frag_quality = analyze_fragment_quality(audio, sr)
                    if frag_quality.anomaly_flags:
                        log(
                            f"  [{text_index}/{text_total}] anomalías detectadas: "
                            f"{', '.join(frag_quality.anomaly_flags)}"
                        )
                except Exception as exc:
                    log(f"  [{text_index}/{text_total}] aviso: optimización de audio falló: {exc}")
                # -------------------------------------------------------
                # Escritura atómica: archivo temporal en mismo directorio + rename
                # Evita wavs corruptos si el job muere a mitad de escritura.
                tmp_fd, tmp_path = tempfile.mkstemp(
                    dir=str(cache_file.parent), suffix=".tmp.wav"
                )
                os.close(tmp_fd)
                try:
                    sf.write(tmp_path, audio, sr, subtype="PCM_16")
                    # Validar integridad del archivo recién escrito antes de promoverlo
                    validate_audio_file(Path(tmp_path), require_non_silent=True)
                    os.replace(tmp_path, cache_file)
                except Exception:
                    try:
                        os.unlink(tmp_path)
                    except FileNotFoundError:
                        pass
                    raise
                store.add_fragment(
                    digest,
                    engine.name,
                    profile["id"],
                    chunk_text,
                    cache_file,
                    audio_s,
                    spent,
                    attempt=attempt,
                    ok=good,
                )
                generated += 1
                compute_total += spent
                if tries > 1:
                    retried += 1
                if not good:
                    doubtful += 1

                temp = cpu_temp_c()
                temp_txt = f", CPU {temp:.0f} °C" if temp is not None else ""
                flag = "" if good else " (sigue anómalo: revísalo al escuchar)"
                log(
                    f"[{text_index}/{text_total}] generado: {audio_s:.1f} s de audio en "
                    f"{spent:.1f} s{temp_txt}{flag}"
                )
                
                fragments_processed += 1
                
                # Actualizar progreso si tenemos project_name
                if project_name and chapter_id is not None:
                    store.update_project_progress(
                        project_name, chapter_id,
                        total_fragments=text_total,
                        processed_fragments=fragments_processed,
                        current_fragment=text_index,
                        status="running"
                    )

            parts.append(np.asarray(audio, dtype=np.float32))

            # Pausa automática solo entre dos segmentos de texto.
            # Si el siguiente segmento es una pausa explícita, no añadimos pausa automática:
            # la pausa del autor manda.
            next_seg = segments[seg_pos + 1] if seg_pos + 1 < len(segments) else None
            if next_seg is not None and next_seg.kind == "text":
                pause_ms = settings.paragraph_pause_ms if paragraph_end else settings.pause_ms
                parts.append(np.zeros(int(sr * pause_ms / 1000), dtype=np.float32))

    finally:
        # No descargamos el motor: es un singleton que vive entre narraciones
        # en el mismo proceso. gc.collect() en unload() ya libera memoria.
        
        # Marcar progreso como fallido si hubo excepción
        if project_name and chapter_id is not None:
            if fragments_processed < text_total:
                store.update_project_progress(
                    project_name, chapter_id,
                    total_fragments=text_total,
                    processed_fragments=fragments_processed,
                    current_fragment=text_index,
                    status="failed",
                    error_message="Narración interrumpida"
                )

    final = assemble_final_audio(
        parts, sr, crossfade_ms=getattr(settings, "crossfade_ms", 10.0)
    ) if parts else np.zeros(0, dtype=np.float32)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        _export_audio(final, sr, out_path)
    except Exception as e:
        # Marcar como fallido si no se pudo exportar
        if project_name and chapter_id is not None:
            store.update_project_progress(
                project_name, chapter_id,
                total_fragments=text_total,
                processed_fragments=fragments_processed,
                current_fragment=text_index,
                status="failed",
                error_message=f"Error al exportar: {e}"
            )
        raise

    # Marcar como completado si todo fue bien
    if project_name and chapter_id is not None and fragments_processed >= text_total:
        store.update_project_progress(
            project_name, chapter_id,
            total_fragments=text_total,
            processed_fragments=fragments_processed,
            current_fragment=text_index,
            status="completed",
            finished_at=_now()
        )

    # Aplicar normalización EBU R128 si está configurada
    if hasattr(settings, 'apply_ebu_r128') and settings.apply_ebu_r128:
        try:
            from .voicefx import normalize_lufs
            # Crear un archivo temporal para la normalización
            temp_normalized = out_path.with_name(out_path.stem + ".ebu_norm.wav")
            
            # Aplicar normalización EBU R128
            normalize_lufs(
                out_path, temp_normalized,
                target_lufs=settings.target_lufs,
                true_peak=settings.target_true_peak,
                lra=settings.target_lra,
                force=True
            )
            
            # Reemplazar el archivo original
            temp_normalized.replace(out_path)
            
            logger.info(
                f"Normalización EBU R128 aplicada: "
                f"LUFS={settings.target_lufs}, TP={settings.target_true_peak}, LRA={settings.target_lra}"
            )
            
        except Exception as e:
            logger.warning(f"No se pudo aplicar normalización EBU R128: {e}")
            # No fallar si la normalización no funciona
            pass

    return NarrationResult(
        out_path,
        text_total,
        generated,
        cached,
        retried,
        doubtful,
        len(final) / sr,
        compute_total,
        waited_total,
        pause_total,
    )