"""Línea de comandos de VoxForge Local."""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import soundfile as sf

from .importers import extract_text, ImporterError, PDF_EXTS, BINARY_IMPORT_EXTS
from .pronunciation import PronunciationError, load_pronunciation
from .bookimport import BookImportError, prepare_book_parts, DEFAULT_HARD_MAX_CHARS, DEFAULT_TARGET_CHARS
from .pausetext import PauseError, parse_blocks, pause_count, total_pause_seconds
from .textutil import split_segments

from . import __version__
from . import recorder
from .prepare import PrepareError, prepare
from .similarity import compare
from .audioqa import analyze, format_report, room_noise
from .config import home, load_settings
from .db import Store
from .thermal import cpu_temp_c
from .voice_delete import delete_voice, ProfileNotFound


# =============================================================================
# NOVA Theme Support for CLI
# =============================================================================
# Global variable to store NOVA CLI theme (set in main())
NOVA_CLI = None


def nova_print(message: str, level: str = "info", end: str = "\n", file=None) -> None:
    """Print with NOVA theme colors if available.
    
    Args:
        message: The message to print
        level: One of 'title', 'header', 'success', 'warning', 'error', 'info', 'muted', 'accent'
        end: End character (default: '\n')
        file: File to write to (default: sys.stdout)
    """
    if NOVA_CLI:
        color_func = getattr(NOVA_CLI, level, NOVA_CLI.info)
        colored_message = color_func(message)
        print(colored_message, end=end, file=file)
    else:
        print(message, end=end, file=file)


def nova_format(message: str, level: str = "info") -> str:
    """Format message with NOVA theme colors if available.
    
    Args:
        message: The message to format
        level: One of 'title', 'header', 'success', 'warning', 'error', 'info', 'muted', 'accent'
    
    Returns:
        Formatted message (with ANSI codes if NOVA_CLI available)
    """
    if NOVA_CLI:
        color_func = getattr(NOVA_CLI, level, NOVA_CLI.info)
        return color_func(message)
    return message


def print_error(message: str, file=None) -> None:
    """Print error message with NOVA theme if available."""
    if NOVA_CLI:
        print(f"{NOVA_CLI.error('✗ Error:')} {message}", file=file or sys.stderr)
    else:
        print(f"Error: {message}", file=file or sys.stderr)


def print_success(message: str) -> None:
    """Print success message with NOVA theme if available."""
    if NOVA_CLI:
        nova_print(f"✓ {message}", "success")
    else:
        print(f"✓ {message}")


def print_warning(message: str) -> None:
    """Print warning message with NOVA theme if available."""
    if NOVA_CLI:
        nova_print(f"⚠ {message}", "warning")
    else:
        print(f"⚠ {message}")


def print_info(message: str) -> None:
    """Print info message with NOVA theme if available."""
    if NOVA_CLI:
        nova_print(f"ℹ {message}", "info")
    else:
        print(f"ℹ {message}")
from .voicefx import PRESETS, apply_fx, analyze_audio, batch_process, format_analysis, FxError, normalize_lufs
from .projects import (
    add_chapter,
    ChapterNotFound,
    create_project,
    delete_project,
    get_chapter,
    get_project,
    list_chapters,
    list_chapters_full,
    list_projects,
    ProjectError,
    ProjectNotFound,
)
from .services import (
    ProjectService,
    VoiceManagerService,
    ProjectRequest,
    ChapterRequest,
    ProjectResponse,
    VoiceProfileRequest,
    VoiceProfileResponse,
)
from .services.narrator import NarratorService, NarrationRequest

_NAME_RE = re.compile(r"^[\w-]+$")

READING_TEXT = (
    "Cuando amanece en la costa, el mar parece una hoja de papel recién planchada. "
    "Los pescadores preparan las redes mientras hablan de la marea, del viento y de lo caro "
    "que está todo. ¿Quién diría que una mañana tan simple podría guardar tantas historias? "
    "Yo prefiero caminar despacio, respirar hondo y escuchar cómo las gaviotas discuten con las olas."
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _convert_to_wav24(src: Path, dest: Path) -> str | None:
    """Convierte a WAV mono 24 kHz con ffmpeg. Devuelve None si va bien, o el error."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "24000", str(dest)],
            capture_output=True,
            text=True,
            check=True,
        )
        return None
    except subprocess.CalledProcessError as e:
        return e.stderr if e.stderr else f"ffmpeg fallo con codigo {e.returncode}"


def _summary(checks) -> str:
    values = {c.name: c.value for c in checks}
    return (
        f"duración {values['Duración']} | "
        f"ruido {values.get('Ruido de fondo', 'n/d')} | "
        f"señal/ruido {values.get('Relación señal/ruido', 'n/d')}"
    )


def _load_mono24(path: Path):
    """Lee cualquier audio como mono 24 kHz float32 vía ffmpeg. Devuelve (audio, sr) o (None, error)."""
    with tempfile.TemporaryDirectory() as tmp:
        converted = Path(tmp) / "audio.wav"
        error = _convert_to_wav24(path, converted)
        if error:
            return None, error
        audio, sr = sf.read(converted, dtype="float32")
    return audio, sr


def _slug(text: str) -> str:
    s = re.sub(r"[^\w]+", "_", text.strip().lower(), flags=re.UNICODE)
    return re.sub(r"_+", "_", s).strip("_")[:60] or "capitulo"


def _get_services(data_dir: Path, settings, store) -> tuple[ProjectService, VoiceManagerService, NarratorService]:
    """Inicializa y devuelve los servicios compartidos."""
    project_service = ProjectService(
        store=store,
        settings=settings,
        data_dir=data_dir
    )
    voice_service = VoiceManagerService(
        store=store,
        settings=settings,
        data_dir=data_dir
    )
    narrator_service = NarratorService(
        store=store,
        settings=settings,
        data_dir=data_dir,
        cache_dir=data_dir / "cache",
        export_dir=data_dir / "exports"
    )
    return project_service, voice_service, narrator_service


def _resolve_project_profile(store, project_name: str, data_dir: Path):
    """Devuelve (perfil_dict, language_proyecto) o SystemExit con mensaje claro."""
    p = get_project(data_dir / "voxforge.db", project_name)
    profile = store.get_profile(p["voice_profile"])
    if profile is None:
        print(
            f"El proyecto '{project_name}' apunta a la voz '{p['voice_profile']}', "
            "que ya no existe. Crea el perfil o edita el proyecto.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return profile, p["language"]


# --------------------------------------------------------------------------- #
# Helpers de pronunciación                                                     #
# --------------------------------------------------------------------------- #

def _add_pron_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pronunciation",
        help="ruta del diccionario JSON (por defecto data/pronunciation.json si existe)",
    )
    parser.add_argument(
        "--pron-lang",
        help="packs separados por comas, p. ej. base,nah,zh,en,hi,fr",
    )
    parser.add_argument(
        "--no-pronunciation",
        action="store_true",
        help="no aplicar diccionario de pronunciación",
    )


def _parse_pron_langs(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [x.strip() for x in value.split(",") if x.strip()]


def _load_pron_config(args, data_dir: Path):
    if getattr(args, "no_pronunciation", False):
        return None, None

    explicit = getattr(args, "pronunciation", None)
    path = Path(explicit).expanduser() if explicit else data_dir / "pronunciation.json"

    try:
        cfg = load_pronunciation(path, required=bool(explicit))
    except PronunciationError as exc:
        print(f"Error de diccionario: {exc}", file=sys.stderr)
        raise SystemExit(1)

    langs = _parse_pron_langs(getattr(args, "pron_lang", None))
    return cfg, langs


def _apply_pronunciation(text: str, cfg, langs, *, log=print) -> str:
    if cfg is None:
        return text
    try:
        out = cfg.apply(text, langs)
    except PronunciationError as exc:
        print(f"Error de diccionario: {exc}", file=sys.stderr)
        raise SystemExit(1)
    if out != text:
        log("Diccionario de pronunciación aplicado.")
    return out


# --------------------------------------------------------------------------- #
# status                                                                       #
# --------------------------------------------------------------------------- #

def _add_fx_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fx",
        choices=sorted(PRESETS),
        help="aplicar un preset de Voice FX al archivo exportado",
    )
    parser.add_argument(
        "--fx-gain-db",
        type=float,
        default=0.0,
        help="ajuste de ganancia aplicado antes del preset (dB)",
    )

def _voxforge_job_store(data_dir: Path):
    from .jobs import JobStore
    return JobStore(data_dir / "voxforge.db", data_dir)


def _job_command_display(command_json: str | None) -> str:
    import json

    try:
        cmd = json.loads(command_json or "[]")
        return " ".join(str(x) for x in cmd)
    except Exception:
        return command_json or ""


def cmd_job_start(args, data_dir, settings, store) -> int:
    import json
    import os
    import subprocess
    import sys

    from .jobs import JobError

    command = list(args.command or [])
    if command and command[0] == "--":
        command = command[1:]

    # Si el usuario incluye accidentalmente "python -m voxforge", lo quitamos.
    if (
        len(command) >= 3
        and command[0] in ("python", "python3", sys.executable)
        and command[1] == "-m"
        and command[2] == "voxforge"
    ):
        command = command[3:]

    if not command:
        print(
            "Indica un comando tras --. Ejemplo: "
            "python -m voxforge job start -- status",
            file=sys.stderr,
        )
        return 2

    kind = str(command[0])
    project = args.project
    ordinal = args.ordinal

    # Inferir proyecto/capítulo cuando sea posible, para evitar solapamientos.
    if project is None:
        if (
            kind == "chapter"
            and len(command) >= 4
            and command[1] in {"narrate", "regen", "fragments", "pauses", "list"}
        ):
            project = str(command[2])
            try:
                ordinal = int(command[3])
            except Exception:
                ordinal = None
        elif kind == "project-narrate" and len(command) >= 2:
            project = str(command[1])

    full_command = [sys.executable, "-m", "voxforge"] + [str(x) for x in command]
    project_root = Path(__file__).resolve().parents[1]

    job_store = _voxforge_job_store(data_dir)

    try:
        if project is not None and not args.allow_duplicate:
            active = job_store.active_jobs(project=project, ordinal=ordinal)
            if active:
                print(
                    "Ya hay trabajos activos para este proyecto/capítulo. "
                    "Usa --allow-duplicate si es intencional.",
                    file=sys.stderr,
                )
                for j in active[:10]:
                    print(
                        f"  id={j['id']} status={j['status']} kind={j['kind']} "
                        f"project={j['project']} ordinal={j['ordinal']} pid={j['pid']}",
                        file=sys.stderr,
                    )
                return 2

        job_id, log_path = job_store.create_job(
            kind=kind,
            command=full_command,
            cwd=str(project_root),
            name=args.name,
            project=project,
            ordinal=ordinal,
            meta={"source_command": command},
        )
    except JobError as exc:
        print(f"Error de trabajo: {exc}", file=sys.stderr)
        return 1

    runner_cmd = [
        sys.executable,
        "-m",
        "voxforge",
        "job",
        "run",
        "--id",
        str(job_id),
        "--",
    ] + full_command

    try:
        log_file = open(log_path, "ab", buffering=0)
    except OSError as exc:
        print(f"No se pudo abrir el log del trabajo: {exc}", file=sys.stderr)
        return 1

    try:
        proc = subprocess.Popen(
            runner_cmd,
            cwd=str(project_root),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception as exc:
        log_file.close()
        try:
            job_store.finish(
                job_id,
                "failed",
                None,
                note=f"no se pudo lanzar el runner: {exc}",
            )
        except Exception:
            pass
        print(f"No se pudo lanzar el trabajo: {exc}", file=sys.stderr)
        return 1
    finally:
        log_file.close()

    try:
        pgid = os.getpgid(proc.pid)
    except Exception:
        pgid = None

    job_store.mark_running(job_id, proc.pid, pgid)

    print(f"Trabajo iniciado: id={job_id} status=running pid={proc.pid}")
    print(f"Log: {log_path}")
    print(f"Ver: python -m voxforge job show {job_id}")
    print(f"Logs: python -m voxforge job logs {job_id} --tail 80")
    return 0


def cmd_job_run(args, data_dir, settings, store) -> int:
    import json
    import os
    import signal
    import subprocess

    from .jobs import JobStore

    job_store = JobStore(data_dir / "voxforge.db", data_dir)
    job = job_store.get_job(args.id)

    if job is None:
        print(f"No existe el trabajo {args.id}.", file=sys.stderr)
        return 1

    try:
        command = json.loads(job["command"])
    except Exception as exc:
        job_store.finish(args.id, "failed", None, note=f"comando inválido: {exc}")
        print(f"Comando inválido en el trabajo {args.id}: {exc}", file=sys.stderr)
        return 1

    log_path = Path(job["log_path"] or (data_dir / "jobs" / f"{job['id']:05d}.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    child_ref: list[subprocess.Popen] = []

    def _terminate(signum, frame):
        child = child_ref[0] if child_ref else None
        if child is not None and child.poll() is None:
            try:
                child.terminate()
            except Exception:
                pass

    old_term = signal.signal(signal.SIGTERM, _terminate)
    old_int = signal.signal(signal.SIGINT, _terminate)

    try:
        with open(log_path, "ab", buffering=0) as log_file:
            def write(msg: str) -> None:
                log_file.write((str(msg) + "\n").encode("utf-8", errors="replace"))

            write(f"[voxforge-job] runner pid={os.getpid()} job={job['id']}")

            child = subprocess.Popen(
                command,
                cwd=job["cwd"],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
            child_ref.append(child)
            job_store.mark_child_pid(job["id"], child.pid)

            try:
                exit_code = child.wait()
            except Exception as exc:
                write(f"[voxforge-job] error esperando proceso: {exc}")
                job_store.finish(job["id"], "failed", None, note=str(exc))
                return 1

            if exit_code == 0:
                status = "succeeded"
                note = ""
            elif exit_code in (-signal.SIGTERM, -signal.SIGINT, 143, 130):
                status = "canceled"
                note = "terminado por señal"
            else:
                status = "failed"
                note = ""

            job_store.finish(job["id"], status, exit_code, note=note)
            write(f"[voxforge-job] finished status={status} exit_code={exit_code}")

        return 0 if status == "succeeded" else 1
    finally:
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)


def cmd_job_list(args, data_dir, settings, store) -> int:
    job_store = _voxforge_job_store(data_dir)
    jobs = job_store.list_jobs(limit=args.limit, status=args.status, project=args.project)

    if not jobs:
        print("No hay trabajos.")
        return 0

    print(
        f"{'ID':>5}  {'ESTADO':<10}  {'TIPO':<16}  {'PROYECTO':<18}  "
        f"{'CAP':>4}  {'PID':>8}  {'SALIDA':>6}  {'INICIO':<20}  {'FIN':<20}"
    )
    print("-" * 118)

    for j in jobs:
        started = (j.get("started_at") or "")[:19]
        finished = (j.get("finished_at") or "")[:19]
        ordinal = j.get("ordinal")
        ordinal_txt = str(ordinal) if ordinal is not None else "-"
        exit_code = j.get("exit_code")
        exit_txt = str(exit_code) if exit_code is not None else "-"

        print(
            f"{j['id']:>5}  "
            f"{j['status']:<10}  "
            f"{(j.get('kind') or '-'):<16}  "
            f"{(j.get('project') or '-'):<18}  "
            f"{ordinal_txt:>4}  "
            f"{(j.get('pid') or '-')!s:>8}  "
            f"{exit_txt:>6}  "
            f"{started:<20}  "
            f"{finished:<20}"
        )

    return 0


def _decode_json(value, default):
    import json

    if not value:
        return default

    try:
        return json.loads(value)
    except Exception:
        return default


def cmd_job_show(args, data_dir, settings, store) -> int:
    import json

    job_store = _voxforge_job_store(data_dir)
    job = job_store.get_job(args.id)

    if job is None:
        print(f"No existe el trabajo {args.id}.", file=sys.stderr)
        return 2

    print(f"Trabajo {job['id']}")
    print(f"  nombre:      {job.get('name') or '-'}")
    print(f"  tipo:        {job.get('kind') or '-'}")
    print(f"  estado:      {job.get('status')}")
    print(f"  proyecto:    {job.get('project') or '-'}")
    print(f"  capítulo:    {job.get('ordinal') if job.get('ordinal') is not None else '-'}")
    print(f"  pid runner:  {job.get('pid') or '-'}")
    print(f"  pgid:        {job.get('pgid') or '-'}")
    print(f"  pid hijo:    {job.get('child_pid') or '-'}")
    print(f"  creada:      {job.get('created_at') or '-'}")
    print(f"  iniciada:    {job.get('started_at') or '-'}")
    print(f"  terminada:   {job.get('finished_at') or '-'}")
    print(f"  exit code:   {job.get('exit_code') if job.get('exit_code') is not None else '-'}")
    print(f"  nota:        {job.get('note') or '-'}")
    print(f"  log:         {job.get('log_path') or '-'}")
    print(f"  cwd:         {job.get('cwd') or '-'}")
    print()
    print("Comando:")
    try:
        cmd = json.loads(job.get("command") or "[]")
        print("  " + " ".join(str(x) for x in cmd))
    except Exception:
        print(f"  {job.get('command')}")

    meta = _decode_json(job.get("meta"), {})
    if meta:
        print()
        print("Meta:")
        print(f"  {meta}")

    return 0


def cmd_job_logs(args, data_dir, settings, store) -> int:
    from collections import deque

    job_store = _voxforge_job_store(data_dir)
    job = job_store.get_job(args.id)

    if job is None:
        print(f"No existe el trabajo {args.id}.", file=sys.stderr)
        return 2

    log_path = Path(job.get("log_path") or "")
    if not log_path.is_file():
        print("(sin log disponible)")
        return 0

    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        tail = deque(f, maxlen=args.tail)

    for line in tail:
        print(line, end="")

    return 0


def cmd_job_cancel(args, data_dir, settings, store) -> int:
    job_store = _voxforge_job_store(data_dir)

    try:
        ok = job_store.cancel(args.id)
    except Exception as exc:
        print(f"Error cancelando el trabajo: {exc}", file=sys.stderr)
        return 1

    if ok:
        print(f"Trabajo cancelado: {args.id}")
    else:
        job = job_store.get_job(args.id)
        if job is None:
            print(f"No existe el trabajo {args.id}.", file=sys.stderr)
            return 2
        print(f"El trabajo {args.id} ya no está activo (estado: {job['status']}).")

    return 0


def cmd_job_cleanup(args, data_dir, settings, store) -> int:
    job_store = _voxforge_job_store(data_dir)

    if args.all_finished:
        count = job_store.delete_finished(older_than_days=None)
    else:
        count = job_store.delete_finished(older_than_days=args.days)

    print(f"Trabajos terminados eliminados: {count}")
    return 0


def cmd_status(args, data_dir, settings, store) -> int:
    temp = cpu_temp_c()
    
    if NOVA_CLI:
        # NOVA Theme: Formatted output with colors
        nova_print(f"VoxForge Local {__version__}", "title")
        nova_print(f"Datos: {data_dir}")
        temp_str = f"{temp:.0f} °C" if temp is not None else "sin sensor"
        nova_print(f"Temperatura CPU: {temp_str}")
        nova_print(
            f"Perfiles de voz: {len(store.list_profiles())} | "
            f"Fragmentos en caché: {store.fragment_count()}"
        )
        if settings.thermal_guard:
            nova_print(
                f"Guardia térmica: activa (pausa a {settings.temp_pause_c:.0f} °C, "
                f"reanuda a {settings.temp_resume_c:.0f} °C)"
            )
        else:
            nova_print("Guardia térmica: desactivada")
    else:
        # Default output
        print(f"VoxForge Local {__version__}")
        print(f"Datos: {data_dir}")
        print(f"Temperatura CPU: {f'{temp:.0f} °C' if temp is not None else 'sin sensor'}")
        print(
            f"Perfiles de voz: {len(store.list_profiles())} | "
            f"Fragmentos en caché: {store.fragment_count()}"
        )
        if settings.thermal_guard:
            print(
                f"Guardia térmica: activa (pausa a {settings.temp_pause_c:.0f} °C, "
                f"reanuda a {settings.temp_resume_c:.0f} °C)"
            )
        else:
            print("Guardia térmica: desactivada")
    return 0


# --------------------------------------------------------------------------- #
# voice                                                                        #
# --------------------------------------------------------------------------- #

def cmd_voice_add(args, data_dir, settings, store) -> int:
    if not _NAME_RE.match(args.name):
        print_error("El nombre solo puede tener letras, números, guiones y guion bajo.")
        return 2

    src = Path(args.wav).expanduser()
    if not src.is_file():
        print_error(f"No existe el archivo: {src}")
        return 2

    if store.get_profile(args.name):
        print_error(f"Ya existe un perfil llamado '{args.name}'.")
        return 2

    dest_dir = data_dir / "voices" / args.name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "ref.wav"

    error = _convert_to_wav24(src, dest)
    if error:
        print(f"ffmpeg no pudo convertir la muestra:\n{error}", file=sys.stderr)
        return 1

    seconds = sf.info(dest).duration
    audio, sr = sf.read(dest, dtype="float32")
    print(format_report(analyze(audio, sr)))

    store.add_profile(args.name, dest, _sha256(dest), args.language or settings.language)
    print(f"Perfil '{args.name}' creado ({seconds:.1f} s de muestra).")
    return 0


def cmd_voice_check(args, data_dir, settings, store) -> int:
    if bool(args.wav) == bool(args.profile):
        print("Indica un archivo o --profile NOMBRE (solo uno de los dos).", file=sys.stderr)
        return 2

    if args.profile:
        profile = store.get_profile(args.profile)
        if profile is None:
            print(f"No existe el perfil '{args.profile}'.", file=sys.stderr)
            return 2
        audio, sr = sf.read(profile["ref_path"], dtype="float32")
        print(f"Muestra del perfil '{args.profile}':")
    else:
        src = Path(args.wav).expanduser()
        if not src.is_file():
            print(f"No existe el archivo: {src}", file=sys.stderr)
            return 2
        with tempfile.TemporaryDirectory() as tmp:
            converted = Path(tmp) / "muestra.wav"
            error = _convert_to_wav24(src, converted)
            if error:
                print(f"ffmpeg no pudo leer el archivo:\n{error}", file=sys.stderr)
                return 1
            audio, sr = sf.read(converted, dtype="float32")
        print(f"Muestra {src}:")

    print(format_report(analyze(audio, sr)))
    return 0


def cmd_voice_record(args, data_dir, settings, store) -> int:
    if not _NAME_RE.match(args.name):
        print("El nombre solo puede tener letras, números, guiones y guion bajo.", file=sys.stderr)
        return 2

    in_args = recorder.input_args(args.source)
    samples_dir = data_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    out = samples_dir / f"{args.name}_{datetime.now():%Y%m%d_%H%M%S}.wav"

    print("Consejos: sala silenciosa (sin ventiladores), a unos 15 cm del micrófono, tono natural.")
    print("Lee en voz alta este texto (unos 25 s) y pulsa Enter al terminar:\n")
    print(f"  {READING_TEXT}\n")

    try:
        if not args.skip_room_check:
            input("Pulsa Enter y guarda SILENCIO 3 segundos para medir el ruido de la sala... ")
            with tempfile.TemporaryDirectory() as tmp:
                room = Path(tmp) / "sala.wav"
                recorder.record_fixed(in_args, room, 3)
                audio, _ = sf.read(room, dtype="float32")
            check = room_noise(audio)
            print(
                f"  {check.name}: {check.value}  {check.status}"
                + (f"  -> {check.advice}" if check.advice else "")
            )
            if check.status == "MAL" and input(
                "El ambiente no es bueno. ¿Grabar de todos modos? [s/N] "
            ).strip().lower() not in ("s", "si", "sí"):
                print("Cancelado: mejora el ambiente y vuelve a intentarlo.")
                return 1

        input("Pulsa Enter para empezar (cuenta atrás de 3 s)... ")
        for n in (3, 2, 1):
            print(f"  {n}...", flush=True)
            time.sleep(1)
        recorder.record_until(
            in_args, out, lambda: input("● GRABANDO. Lee el texto y pulsa Enter al terminar. ")
        )
    except recorder.RecordingError as exc:
        print(f"No se pudo grabar: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 130

    with tempfile.TemporaryDirectory() as tmp:
        converted = Path(tmp) / "toma.wav"
        error = _convert_to_wav24(out, converted)
        if error:
            print(f"ffmpeg no pudo leer la toma:\n{error}", file=sys.stderr)
            return 1
        audio, sr = sf.read(converted, dtype="float32")

    print(f"\nToma guardada: {out}")
    print(format_report(analyze(audio, sr)))
    print(f"\nSi te convence: python -m voxforge voice add NOMBRE_DEL_PERFIL {out}")
    return 0


def cmd_voice_prepare(args, data_dir, settings, store) -> int:
    if bool(args.wav) == bool(args.profile):
        print("Indica un archivo o --profile NOMBRE (solo uno de los dos).", file=sys.stderr)
        return 2

    if args.profile:
        profile = store.get_profile(args.profile)
        if profile is None:
            print(f"No existe el perfil '{args.profile}'.", file=sys.stderr)
            return 2
        src = Path(profile["ref_path"])
    else:
        src = Path(args.wav).expanduser()
        if not src.is_file():
            print(f"No existe el archivo: {src}", file=sys.stderr)
            return 2

    out = (
        Path(args.out).expanduser()
        if args.out
        else data_dir / "samples" / f"{src.parent.name if args.profile else src.stem}_limpia.wav"
    )

    if out.exists() and not args.force:
        print(
            f"Ya existe {out}. Usa --force para sobrescribirlo o elige otro --out.",
            file=sys.stderr,
        )
        return 2

    try:
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original.wav"
            error = _convert_to_wav24(src, original)
            if error:
                print(f"ffmpeg no pudo leer la muestra:\n{error}", file=sys.stderr)
                return 1
            audio, sr = sf.read(original, dtype="float32")
            before = analyze(audio, sr)
        result = prepare(src, out, nr=args.nr)
    except PrepareError as exc:
        print(f"No se pudo preparar la muestra: {exc}", file=sys.stderr)
        return 1

    audio, sr = sf.read(out, dtype="float32")
    after = analyze(audio, sr)

    print(f"Antes  : {_summary(before)}")
    print(f"Después: {_summary(after)}")
    print(
        f"(reducción de ruido {'desactivada' if args.nr <= 0 else f'{args.nr:g} dB'}, "
        f"ganancia aplicada {result.gain_db:+.1f} dB)"
    )
    print(f"\nMuestra preparada: {out}")
    print(format_report(after))
    print(f"\nPara probarla: python -m voxforge voice add NOMBRE_DEL_PERFIL {out}")
    return 0


def cmd_voice_similarity(args, data_dir, settings, store) -> int:
    from .engines.base import ModelUnavailableError
    from .engines.xtts import XttsEngine

    paths = [Path(args.ref).expanduser()] + [Path(f).expanduser() for f in args.files]
    for path in paths:
        if not path.is_file():
            print(f"No existe el archivo: {path}", file=sys.stderr)
            return 2

    engine = XttsEngine(threads=settings.threads)
    try:
        print("Cargando el modelo para usar su codificador de voz...")
        engine.load()
        ref_audio, ref_sr = _load_mono24(paths[0])
        if ref_audio is None:
            print(f"ffmpeg no pudo leer la referencia:\n{ref_sr}", file=sys.stderr)
            return 1
        ref_emb = engine.speaker_embedding(ref_audio, ref_sr)
        ceiling = compare(engine.speaker_embedding, ref_emb, ref_audio, ref_sr, args.window)
        print(f"\nReferencia: {paths[0]}")
        print(
            f"  {'(la propia referencia, techo)':<32} "
            f"media {ceiling.mean:.3f}  mínima {ceiling.minimum:.3f}  "
            f"({ceiling.windows} ventanas de {args.window:g} s)"
        )
        for path in paths[1:]:
            audio, sr = _load_mono24(path)
            if audio is None:
                print(f"  {path.name}: ffmpeg no pudo leerlo ({sr})", file=sys.stderr)
                continue
            r = compare(engine.speaker_embedding, ref_emb, audio, sr, args.window)
            print(
                f"  {path.name:<32} "
                f"media {r.mean:.3f}  mínima {r.minimum:.3f}  "
                f"({r.windows} ventanas de {args.window:g} s)"
            )
    except ModelUnavailableError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    finally:
        engine.unload()
    print("\nMás alto = más parecido a la referencia. 'Mínima' baja si hay tramos que se desvían (consistencia).")
    return 0


def cmd_voice_list(args, data_dir, settings, store) -> int:
    profiles = store.list_profiles()
    if not profiles:
        print("No hay perfiles. Crea uno con: python -m voxforge voice add NOMBRE muestra.wav")
        return 0
    for p in profiles:
        print(f"{p['name']:<20} idioma={p['language']}  muestra={p['ref_path']}")
    return 0


def cmd_voice_delete(args, data_dir, settings, store) -> int:
    try:
        result = delete_voice(
            args.name,
            yes=args.yes,
            purge_source=args.source,
            shred=args.shred,
            db_path=data_dir / "voxforge.db",
        )
    except ProfileNotFound as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error preparando el borrado: {exc}", file=sys.stderr)
        return 1

    if result.get("dry_run"):
        print(f"Dry-run: no se ha eliminado nada para '{result['profile']}'.")
        print()
        print("Filas relacionadas que se borrarían:")
        if result["db_rows_to_delete"]:
            for table, count in sorted(result["db_rows_to_delete"].items()):
                print(f"  {table}: {count}")
        else:
            print("  Ninguna detectada.")
        print()
        print("Archivos que se borrarían:")
        if result["files_to_delete"]:
            for path in result["files_to_delete"]:
                print(f"  {path}")
        else:
            print("  Ninguno detectado.")
        print()
        print("Para ejecutar el borrado real:")
        print(f"  python -m voxforge voice delete {result['profile']} --yes")
        return 0

    print(f"Perfil eliminado: {result['profile']}")
    print("Filas eliminadas:")
    if result["deleted_db_rows"]:
        for table, count in sorted(result["deleted_db_rows"].items()):
            print(f"  {table}: {count}")
    else:
        print("  Ninguna.")
    print()
    print("Archivos eliminados:")
    if result["deleted_files"]:
        for path in result["deleted_files"]:
            print(f"  {path}")
    else:
        print("  Ninguno.")
    return 0


# --------------------------------------------------------------------------- #
# text                                                                         #
# --------------------------------------------------------------------------- #

def cmd_text_extract(args, data_dir, settings, store) -> int:
    src = Path(args.file).expanduser()
    try:
        text = extract_text(src, lang=args.lang, log=print)
    except ImporterError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    out = (
        Path(args.out).expanduser()
        if args.out
        else data_dir / "imports" / f"{src.stem}.txt"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")

    chars = len(text)
    print(f"\nTexto extraído: {chars} caracteres (~{chars / 10 / 60:.0f} min de audio estimado)")
    print(f"Guardado en: {out}")
    print(f"Para narrarlo: python -m voxforge speak {out} --voice NOMBRE --out data/exports/X.wav")
    return 0


# --------------------------------------------------------------------------- #
# pron                                                                         #
# --------------------------------------------------------------------------- #

def cmd_pron_packs(args, data_dir, settings, store) -> int:
    cfg, langs = _load_pron_config(args, data_dir)
    if cfg is None:
        print("No hay diccionario en data/pronunciation.json.")
        print("Crea uno o usa --pronunciation RUTA.")
        return 0

    print(f"Diccionario: {cfg.path}")
    print(f"Versión: {cfg.version}")
    print()
    print("Packs disponibles:")
    for lang in cfg.available_languages():
        print(f"  {lang:<8} {len(cfg.packs[lang]):>4} términos")

    active = langs if langs is not None else cfg.default_languages
    try:
        active_tuple, terms = cfg.merged_terms(active)
    except PronunciationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"Activos: {', '.join(active_tuple)}")
    print(f"Términos efectivos tras fusión: {len(terms)}")
    return 0


def cmd_pron_check(args, data_dir, settings, store) -> int:
    cfg, langs = _load_pron_config(args, data_dir)
    if cfg is None:
        print("No hay diccionario activo. Usa --pronunciation RUTA o crea data/pronunciation.json.")
        return 0

    raw = None
    origin = ""

    if args.project and args.chapter is not None:
        try:
            ch = get_chapter(data_dir / "voxforge.db", args.project, args.chapter)
        except (ProjectNotFound, ChapterNotFound) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        raw = ch["text"]
        origin = f"capítulo {args.chapter} del proyecto '{args.project}'"
    elif args.file:
        src = Path(args.file).expanduser()
        if not src.is_file():
            print(f"No existe el archivo: {src}", file=sys.stderr)
            return 2
        if src.suffix.lower() in PDF_EXTS:
            try:
                raw = extract_text(src, lang=args.lang, log=print)
            except ImporterError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
        else:
            raw = src.read_text(encoding="utf-8", errors="replace")
        origin = str(src)
    else:
        print("Indica un archivo o --project NOMBRE --chapter ORDINAL.", file=sys.stderr)
        return 2

    if not raw or not raw.strip():
        print("El texto está vacío.", file=sys.stderr)
        return 2

    try:
        report = cfg.check(raw, langs)
        transformed = cfg.apply(raw, langs)
    except PronunciationError as exc:
        print(f"Error de diccionario: {exc}", file=sys.stderr)
        return 1

    print(f"Origen: {origin}")
    print(f"Texto original: {len(raw)} caracteres")
    print(f"Packs activos: {', '.join(report['languages'])}")
    print(
        f"Términos en diccionario: {report['terms_active']} "
        f"(efectivos tras filtrar redundantes: {report['terms_effective']})"
    )
    print()

    if report["redundant"]:
        print(
            "Entradas redundantes (término = reemplazo, ignoradas): "
            + ", ".join(report["redundant"])
        )
        print("Considera borrarlas del JSON para limpiar el diccionario.")
        print()

    if not report["counts"]:
        print("El diccionario no haría sustituciones en este texto.")
        return 0

    print(
        f"Sustituciones detectadas: {len(report['matches'])} "
        f"en {len(report['counts'])} términos"
    )
    print()
    for item in report["counts"][:50]:
        repl = item["replacement"] or "(eliminar)"
        print(f"  {item['count']:>3} x {item['term']} -> {repl}")
    if len(report["counts"]) > 50:
        print(f"  ... y {len(report['counts']) - 50} términos más.")

    print()
    print(
        f"Texto transformado: {len(transformed)} caracteres "
        f"(delta {len(transformed) - len(raw):+d})"
    )
    return 0


def cmd_pron_audit(args, data_dir, settings, store) -> int:
    cfg, langs = _load_pron_config(args, data_dir)
    if cfg is None:
        print("No hay diccionario activo. Usa --pronunciation RUTA o crea data/pronunciation.json.")
        return 0

    raw = None
    origin = ""

    if args.project and args.chapter is not None:
        try:
            ch = get_chapter(data_dir / "voxforge.db", args.project, args.chapter)
        except (ProjectNotFound, ChapterNotFound) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        raw = ch["text"]
        origin = f"capítulo {args.chapter} del proyecto '{args.project}'"
    elif args.file:
        src = Path(args.file).expanduser()
        if not src.is_file():
            print(f"No existe el archivo: {src}", file=sys.stderr)
            return 2
        if src.suffix.lower() in PDF_EXTS:
            try:
                raw = extract_text(src, lang=args.lang, log=print)
            except ImporterError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
        else:
            raw = src.read_text(encoding="utf-8", errors="replace")
        origin = str(src)
    else:
        print("Indica un archivo o --project NOMBRE --chapter ORDINAL.", file=sys.stderr)
        return 2

    if not raw or not raw.strip():
        print("El texto está vacío.", file=sys.stderr)
        return 2

    try:
        report = cfg.audit(raw, langs, top=args.top)
    except PronunciationError as exc:
        print(f"Error de diccionario: {exc}", file=sys.stderr)
        return 1

    print(f"Origen: {origin}")
    print(f"Packs activos: {', '.join(report['languages'])}")
    print(f"Candidatos capitalizados totales: {report['candidates_total']}")
    print()

    if not report["top"]:
        print("No se encontraron candidatos.")
        return 0

    print(f"{'#':>3}  {'freq':>5}  {'cubierto':<9}  {'propio':<7}  término")
    print("-" * 60)
    for i, item in enumerate(report["top"], start=1):
        cov = "sí" if item["covered"] else "NO"
        prop = "sí" if item["likely_proper"] else "¿?"
        print(f"{i:>3}  {item['count']:>5}  {cov:<9}  {prop:<7}  {item['term']}")

    print()
    n_uncov = report.get("uncovered_total", len(report["uncovered_likely"]))
    print(f"Candidatos probables NO cubiertos por el diccionario: {n_uncov}")
    if n_uncov:
        print("Añádelos al pack 'base' (o crea un pack 'maya') en data/pronunciation.json:")
        print()
        for item in report["uncovered_likely"][:40]:
            print(f'        "{item["term"]}": "",   # freq {item["count"]}')
        if n_uncov > 40:
            print(f'        # ... y {n_uncov - 40} más (sube --top para verlos)')
    return 0

def cmd_project_import(args, data_dir, settings, store) -> int:
    src = Path(args.file).expanduser()

    if not src.is_file():
        print(f"No existe el archivo fuente: {src}", file=sys.stderr)
        return 2

    if store.get_profile(args.voice) is None:
        print(
            f"No existe el perfil de voz '{args.voice}'. "
            "Perfiles disponibles: python -m voxforge voice list",
            file=sys.stderr,
        )
        return 2

    db = data_dir / "voxforge.db"
    parts_dir = (
        Path(args.parts_dir).expanduser()
        if args.parts_dir
        else data_dir / "imports" / f"{args.name}_partes"
    )

    try:
        get_project(db, args.name)
        exists = True
    except ProjectNotFound:
        exists = False

    if exists and not args.replace:
        print(
            f"Ya existe el proyecto '{args.name}'. "
            "Use --replace para recrearlo.",
            file=sys.stderr,
        )
        return 2

    if exists and args.replace:
        try:
            result = delete_project(db, args.name, yes=True)
            print(
                f"Proyecto existente reemplazado: {result['project']} "
                f"({result.get('deleted_chapters', 0)} capítulo(s) borrados)."
            )
        except ProjectNotFound:
            pass
        except ProjectError as exc:
            print(f"Error al reemplazar el proyecto: {exc}", file=sys.stderr)
            return 1

        # Limpia partes anteriores solo si el directorio está bajo data/imports.
        try:
            imports_root = (data_dir / "imports").resolve()
            if parts_dir.exists() and parts_dir.resolve().is_relative_to(imports_root):
                for old in parts_dir.glob("*.txt"):
                    old.unlink()
        except Exception:
            pass

    try:
        parts = prepare_book_parts(
            src,
            parts_dir,
            target_chars=args.target_chars,
            hard_max_chars=args.hard_max_chars,
            lang=args.lang,
            log=lambda m: print(m, flush=True),
        )
    except BookImportError as exc:
        print(f"Error de importación de libro: {exc}", file=sys.stderr)
        return 1
    except ImporterError as exc:
        print(f"Error extrayendo texto: {exc}", file=sys.stderr)
        return 1

    if not parts:
        print("No se generaron partes a partir del libro.", file=sys.stderr)
        return 1

    try:
        project = create_project(
            db,
            args.name,
            args.voice,
            args.language or settings.language,
        )
    except ProjectError as exc:
        print(f"Error creando el proyecto: {exc}", file=sys.stderr)
        return 2

    print(f"\nProyecto '{project['name']}' creado (voz: {project['voice_profile']}, idioma: {project['language']}).")

    added = 0

    for part in parts:
        title = f"Parte {part.number:02d}"

        try:
            ch = add_chapter(
                db,
                args.name,
                title,
                part.path,
                lang=args.lang,
            )
        except (ProjectNotFound, ProjectError) as exc:
            print(f"Error añadiendo el capítulo '{title}': {exc}", file=sys.stderr)
            return 1

        added += 1
        print(f"  capítulo {ch['ordinal']:>3}: {ch['title']} ({ch['chars']} car.)")

    total_chars = sum(part.chars for part in parts)
    total_minutes = total_chars / 10 / 60

    print()
    print(
        f"Importación completada: {added} capítulo(s), "
        f"{total_chars} caracteres, ~{total_minutes:.1f} min de audio estimado."
    )
    print()
    print("Siguiente paso, piloto:")
    print(
        f"  python -m voxforge chapter narrate {args.name} 1 "
        f"--out data/exports/{args.name}/001_piloto.mp3"
    )
    print()
    print("Producción maestra WAV:")
    print(
        f"  python -m voxforge project-narrate {args.name} "
        f"--format wav --out-dir data/exports/{args.name}_wav"
    )

    return 0


def cmd_project_create(args, data_dir, settings, store) -> int:
    project_service, _, _ = _get_services(data_dir, settings, store)
    
    request = ProjectRequest(
        name=args.name,
        voice_profile=args.voice,
        language=args.language or settings.language
    )
    
    response = project_service.create_project(request)
    
    if not response.success:
        print(f"Error: {response.error}", file=sys.stderr)
        return 2
    
    print(f"Proyecto '{args.name}' creado (voz: {args.voice}, idioma: {args.language or settings.language}).")
    return 0


def cmd_project_list(args, data_dir, settings, store) -> int:
    project_service, _, _ = _get_services(data_dir, settings, store)
    projects = project_service.list_projects()
    
    if not projects:
        print("No hay proyectos. Crea uno: python -m voxforge project create NOMBRE --voice yo_limpia")
        return 0
    for p in projects:
        print(
            f"{p['name']:<20} "
            f"voz={p['voice_profile']:<14} "
            f"idioma={p['language'] or '-':<4} "
            f"capítulos={p['chapters']}"
        )
    return 0


def cmd_project_show(args, data_dir, settings, store) -> int:
    project_service, _, _ = _get_services(data_dir, settings, store)
    p = project_service.get_project(args.name)
    
    if not p:
        print(f"Error: No existe el proyecto '{args.name}'", file=sys.stderr)
        return 2
    
    print(f"Proyecto: {p['name']}")
    print(f"  voz:       {p['voice_profile']}")
    print(f"  idioma:    {p['language'] or '-'}")
    print(f"  capítulos: {p['chapters']}")
    return 0


def cmd_project_delete(args, data_dir, settings, store) -> int:
    # Para mantener compatibilidad con la lógica existente, usamos la función directa
    # pero idealmente esto debería ser manejado por ProjectService
    try:
        result = delete_project(data_dir / "voxforge.db", args.name, yes=args.yes)
    except ProjectNotFound as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except ProjectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if result.get("dry_run"):
        print(f"Dry-run: no se ha eliminado nada para el proyecto '{result['project']}'.")
        print(f"  Se borrarían {result['chapters_to_delete']} capítulo(s).")
        print("  NO se toca la voz del perfil ni la caché global de fragmentos.")
        print()
        print("Para ejecutar el borrado real:")
        print(f"  python -m voxforge project delete {result['project']} --yes")
        return 0

    print(
        f"Proyecto eliminado: {result['project']} "
        f"({result['deleted_chapters']} capítulo(s) borrados)."
    )
    return 0


# --------------------------------------------------------------------------- #
# chapter                                                                      #
# --------------------------------------------------------------------------- #

def cmd_chapter_add(args, data_dir, settings, store) -> int:
    project_service, _, _ = _get_services(data_dir, settings, store)
    
    src = Path(args.file).expanduser()
    if not src.is_file():
        print(f"No existe el archivo: {src}", file=sys.stderr)
        return 2
    
    request = ChapterRequest(
        project_name=args.project,
        title=args.title,
        file_path=src,
        text=None
    )
    
    response = project_service.add_chapter(request)
    
    if not response.success:
        print(f"Error: {response.error}", file=sys.stderr)
        return 2
    
    print(
        f"Capítulo añadido a '{args.project}': {args.title} "
        f"(id={response.chapter_id})."
    )
    return 0


def cmd_chapter_list(args, data_dir, settings, store) -> int:
    project_service, _, _ = _get_services(data_dir, settings, store)
    
    chapters = project_service.list_chapters(args.project)
    
    if not chapters:
        print(f"El proyecto '{args.project}' no tiene capítulos.")
        return 0
    for ch in chapters:
        print(f"  {ch['ordinal']:>3}. {ch['title']:<40} ({ch['chars']} car.)")
    return 0


def cmd_chapter_pauses(args, data_dir, settings, store) -> int:
    cfg, pron_langs = _load_pron_config(args, data_dir)

    try:
        ch = get_chapter(data_dir / "voxforge.db", args.project, args.ordinal)
    except (ProjectNotFound, ChapterNotFound) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    text = _apply_pronunciation(ch["text"], cfg, pron_langs)

    try:
        blocks = parse_blocks(text)
    except PauseError as exc:
        print(f"Error de marcas de pausa: {exc}", file=sys.stderr)
        return 1

    tb = [b for b in blocks if b.kind == "text"]
    n_pauses = pause_count(blocks)
    total_s = total_pause_seconds(blocks)
    chars = sum(len(b.text.strip()) for b in tb)

    print(f"Capítulo {args.ordinal} de '{args.project}': {len(blocks)} bloque(s)")
    print(f"  bloques de texto: {len(tb)} ({chars} caracteres útiles)")
    print(f"  pausas explícitas: {n_pauses} ({total_s:.1f} s totales)")
    print()

    if not blocks:
        print("El capítulo está vacío tras quitar marcas.")
        return 0

    for i, b in enumerate(blocks, start=1):
        if b.kind == "text":
            excerpt = " ".join(b.text.split())[:80]
            print(f"  {i:>3}. TEXTO   {len(b.text.strip()):>5} car. | {excerpt}")
        else:
            print(f"  {i:>3}. PAUSA   {b.seconds:>5.1f} s  | [{b.name}={b.seconds:g}s]")

    print()

    if n_pauses == 0:
        print("No se detectaron marcas [pausa=...] o [silencio=...].")
    else:
        print("Nota: la narración ya inserta estas pausas en el audio final.")

    return 0


def cmd_chapter_fragments(args, data_dir, settings, store) -> int:
    cfg, pron_langs = _load_pron_config(args, data_dir)

    try:
        ch = get_chapter(data_dir / "voxforge.db", args.project, args.ordinal)
    except (ProjectNotFound, ChapterNotFound) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    text = _apply_pronunciation(ch["text"], cfg, pron_langs)

    try:
        segments = split_segments(text, settings.max_chunk_chars)
    except PauseError as exc:
        print(f"Error de marcas de pausa: {exc}", file=sys.stderr)
        return 1

    text_total = sum(1 for seg in segments if seg.kind == "text")
    pause_total = len(segments) - text_total

    if text_total == 0 and pause_total == 0:
        print("El capítulo no contiene texto.")
        return 0

    print(
        f"Capítulo {args.ordinal} de '{args.project}': "
        f"{text_total} fragmento(s) de texto + {pause_total} pausa(s)"
    )

    text_index = 0
    for seg in segments:
        if seg.kind == "pause":
            print(f"      PAUSA   {seg.seconds:>5.1f} s  | [{seg.name}={seg.seconds:g}s]")
        else:
            text_index += 1
            excerpt = " ".join(seg.text.split())[:80]
            print(f"  {text_index:>3}. TEXTO   {len(seg.text):>5} car. | {excerpt}")

    return 0


def cmd_chapter_narrate(args, data_dir, settings, store) -> int:
    """Narra un capítulo usando el NarratorService."""
    from .services.narrator import NarratorService, NarrationRequest
    from .utils import SynthCancelledError
    import threading

    cfg, pron_langs = _load_pron_config(args, data_dir)

    try:
        profile, proj_lang = _resolve_project_profile(store, args.project, data_dir)
        ch = get_chapter(data_dir / "voxforge.db", args.project, args.ordinal)
    except (ProjectNotFound, ChapterNotFound) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    text = _apply_pronunciation(ch["text"], cfg, pron_langs)

    final_out = (
        Path(args.out).expanduser()
        if args.out
        else data_dir / "exports" / args.project / f"{args.ordinal:03d}_{_slug(ch['title'])}.mp3"
    )
    
    # Determinar si usar FX
    use_fx = bool(getattr(args, "fx", None))
    narrate_out = final_out.with_name(final_out.stem + ".raw.wav") if use_fx else final_out

    # Crear cancel event (para soporte futuro de cancelación)
    cancel_event = threading.Event()

    try:
        # Usar NarratorService
        narrator = NarratorService(
            store=store,
            settings=settings,
            data_dir=data_dir,
            cache_dir=data_dir / "cache",
            export_dir=data_dir / "exports"
        )
        
        request = NarrationRequest(
            project_name=args.project,
            chapter_id=ch["id"],
            text=text,
            voice_profile_name=profile["name"],
            language=args.language or proj_lang,
            regen=args.regen,
            out_path=narrate_out,
            cancel_event=cancel_event,
            resume=not args.regen,  # Reanudar solo si no es regeneración completa
        )
        
        response = narrator.narrate(request)
        
        if not response.success:
            if response.partial:
                print(f"\nInterrumpido: {response.error}")
                print("Fragmentos ya generados quedan en caché. Puedes reanudar más tarde.")
                return 130
            else:
                print(f"\nError: {response.error}", file=sys.stderr)
                if response.message:
                    print(f"   {response.message}", file=sys.stderr)
                return 1
        
        result = response.result

    except KeyboardInterrupt:
        cancel_event.set()
        print("\nInterrumpido. Fragmentos ya generados quedan en caché.")
        return 130

    if use_fx:
        try:
            apply_fx(
                narrate_out,
                final_out,
                args.fx,
                gain_db=getattr(args, "fx_gain_db", 0.0),
                force=True,
            )
        except FxError as exc:
            print(
                f"Advertencia: audio generado en {narrate_out}, pero falló Voice FX: {exc}",
                file=sys.stderr,
            )
            return 1

        narrate_out.unlink(missing_ok=True)
        print(f"Voice FX aplicado: {args.fx} -> {final_out}")

    print(f"\nListo: {final_out if use_fx else result.out_path}")
    print(
        f"Fragmentos: {result.fragments} ({result.generated} generados, {result.cached} de caché, "
        f"{result.retried} con reintento, {result.doubtful} dudosos)"
    )
    if result.pauses:
        print(f"Pausas explícitas insertadas: {result.pauses}")
    print(
        f"Audio: {result.audio_s:.1f} s | Cálculo: {result.compute_s:.1f} s | "
        f"Pausas térmicas: {result.waited_s:.0f} s"
    )
    return 0


def cmd_chapter_regen(args, data_dir, settings, store) -> int:
    from .engines.base import ModelUnavailableError
    from .engines.xtts import XttsEngine
    from .pipeline import narrate

    cfg, pron_langs = _load_pron_config(args, data_dir)

    try:
        profile, proj_lang = _resolve_project_profile(store, args.project, data_dir)
        ch = get_chapter(data_dir / "voxforge.db", args.project, args.ordinal)
    except (ProjectNotFound, ChapterNotFound) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    text = _apply_pronunciation(ch["text"], cfg, pron_langs)

    try:
        segments = split_segments(text, settings.max_chunk_chars)
    except PauseError as exc:
        print(f"Error de marcas de pausa: {exc}", file=sys.stderr)
        return 1

    text_total = sum(1 for seg in segments if seg.kind == "text")

    if args.fragment < 1 or args.fragment > text_total:
        print(f"El fragmento {args.fragment} está fuera de rango (1-{text_total}).", file=sys.stderr)
        return 2

    final_out = (
        Path(args.out).expanduser()
        if args.out
        else data_dir / "exports" / args.project / f"{args.ordinal:03d}_{_slug(ch['title'])}.mp3"
    )
    final_out.parent.mkdir(parents=True, exist_ok=True)

    use_fx = bool(getattr(args, "fx", None))
    narrate_out = final_out.with_name(final_out.stem + ".raw.wav") if use_fx else final_out

    engine = XttsEngine(threads=settings.threads)

    try:
        result = narrate(
            text,
            profile,
            engine,
            store,
            settings,
            data_dir / "cache",
            narrate_out,
            language=args.language or proj_lang,
            regen_fragment=args.fragment,
            regen_seed=args.seed,
        )
    except PauseError as exc:
        print(f"Error de marcas de pausa: {exc}", file=sys.stderr)
        return 1
    except ModelUnavailableError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrumpido. Lo generado queda en caché.")
        return 130

    if use_fx:
        try:
            apply_fx(
                narrate_out,
                final_out,
                args.fx,
                gain_db=getattr(args, "fx_gain_db", 0.0),
                force=True,
            )
        except FxError as exc:
            print(
                f"Advertencia: audio generado en {narrate_out}, pero falló Voice FX: {exc}",
                file=sys.stderr,
            )
            return 1

        narrate_out.unlink(missing_ok=True)
        print(f"Voice FX aplicado: {args.fx} -> {final_out}")

    print(f"\nListo: {final_out if use_fx else result.out_path}")
    print(
        f"Fragmentos: {result.fragments} ({result.generated} generados, {result.cached} de caché, "
        f"{result.retried} con reintento, {result.doubtful} dudosos)"
    )
    if result.pauses:
        print(f"Pausas explícitas insertadas: {result.pauses}")
    print(
        f"Audio: {result.audio_s:.1f} s | Cálculo: {result.compute_s:.1f} s | "
        f"Pausas térmicas: {result.waited_s:.0f} s"
    )
    return 0


def cmd_project_narrate(args, data_dir, settings, store) -> int:
    from .engines.base import ModelUnavailableError
    from .engines.xtts import XttsEngine
    from .pipeline import narrate

    cfg, pron_langs = _load_pron_config(args, data_dir)

    try:
        profile, proj_lang = _resolve_project_profile(store, args.project, data_dir)
        chapters = list_chapters_full(data_dir / "voxforge.db", args.project)
    except (ProjectNotFound, ChapterNotFound) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not chapters:
        print(f"El proyecto '{args.project}' no tiene capítulos.", file=sys.stderr)
        return 2

    out_dir = (
        Path(args.out_dir).expanduser()
        if args.out_dir
        else data_dir / "exports" / args.project
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = args.format

    use_fx = bool(getattr(args, "fx", None))

    if cfg is not None:
        active = pron_langs if pron_langs is not None else cfg.default_languages
        print(f"Diccionario de pronunciación: {cfg.path}")
        print(f"Packs activos: {', '.join(active)}")

    if use_fx:
        print(f"Voice FX: {args.fx} (gain {getattr(args, 'fx_gain_db', 0.0):+g} dB)")

    engine = XttsEngine(threads=settings.threads)
    totals = {
        "generated": 0,
        "cached": 0,
        "retried": 0,
        "doubtful": 0,
        "audio_s": 0.0,
        "compute_s": 0.0,
        "pauses": 0,
    }

    try:
        for ch in chapters:
            text = _apply_pronunciation(ch["text"], cfg, pron_langs, log=lambda _m: None)
            final_out = out_dir / f"{ch['ordinal']:03d}_{_slug(ch['title'])}.{ext}"
            narrate_out = final_out.with_name(final_out.stem + ".raw.wav") if use_fx else final_out

            print(f"\n=== Capítulo {ch['ordinal']}: {ch['title']} ===")

            result = narrate(
                text,
                profile,
                engine,
                store,
                settings,
                data_dir / "cache",
                narrate_out,
                language=args.language or proj_lang,
                regen=args.regen,
            )

            if use_fx:
                try:
                    apply_fx(
                        narrate_out,
                        final_out,
                        args.fx,
                        gain_db=getattr(args, "fx_gain_db", 0.0),
                        force=True,
                    )
                except FxError as exc:
                    print(
                        f"Advertencia: capítulo generado en {narrate_out}, pero falló Voice FX: {exc}",
                        file=sys.stderr,
                    )
                    return 1

                narrate_out.unlink(missing_ok=True)

            totals["generated"] += result.generated
            totals["cached"] += result.cached
            totals["retried"] += result.retried
            totals["doubtful"] += result.doubtful
            totals["audio_s"] += result.audio_s
            totals["compute_s"] += result.compute_s
            totals["pauses"] += result.pauses

            pause_txt = f", {result.pauses} pausas" if result.pauses else ""
            print(
                f"  -> {final_out.name} | {result.fragments} frag "
                f"({result.generated} gen, {result.cached} caché{pause_txt})"
            )

    except PauseError as exc:
        print(f"Error de marcas de pausa: {exc}", file=sys.stderr)
        return 1
    except ModelUnavailableError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrumpido. Lo generado queda en caché; repite para continuar.")
        return 130

    print(f"\nProyecto '{args.project}' narrado en {out_dir}/ ({ext})")
    print(
        f"Total: {totals['generated']} generados, {totals['cached']} de caché, "
        f"{totals['retried']} con reintento, {totals['doubtful']} dudosos"
    )
    if totals["pauses"]:
        print(f"Pausas explícitas insertadas: {totals['pauses']}")
    print(f"Audio: {totals['audio_s']:.1f} s | Cálculo: {totals['compute_s']:.1f} s")
    return 0


def cmd_fx_presets(args, data_dir, settings, store) -> int:
    print("Presets de Voice FX (v1, ffmpeg):")
    print()
    for name in sorted(PRESETS):
        preset = PRESETS[name]
        print(f"  {preset.name:<12} {preset.description}")
    print()
    print("Ejemplo:")
    print("  python -m voxforge fx apply data/exports/pron_test/001.mp3 \\")
    print("    --preset narracion --out data/exports/pron_test/001_fx.mp3")
    return 0


def cmd_fx_analyze(args, data_dir, settings, store) -> int:
    path = Path(args.audio).expanduser()
    try:
        data = analyze_audio(path)
    except FxError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Análisis: {path}")
    print(format_analysis(data))
    return 0


def cmd_fx_normalize(args, data_dir, settings, store) -> int:
    src = Path(args.audio).expanduser()
    dest = (
        Path(args.out).expanduser()
        if args.out
        else src.with_name(f"{src.stem}_normalized{src.suffix}")
    )

    try:
        out = normalize_lufs(
            src,
            dest,
            target_lufs=args.target_lufs,
            true_peak=args.true_peak,
            lra=args.lra,
            force=args.force,
        )
    except FxError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Audio normalizado: {out}")
    print(f"Objetivo: {args.target_lufs:g} LUFS, TP {args.true_peak:g} dBTP, LRA {args.lra:g} LU")
    print()

    try:
        data = analyze_audio(out)
        print("Análisis de salida:")
        print(format_analysis(data))
    except FxError as exc:
        print(f"(advertencia: no se pudo analizar la salida: {exc})", file=sys.stderr)

    return 0


def cmd_fx_batch(args, data_dir, settings, store) -> int:
    src_dir = Path(args.dir).expanduser()
    out_dir = (
        Path(args.out_dir).expanduser()
        if args.out_dir
        else src_dir / "processed"
    )

    try:
        result = batch_process(
            src_dir,
            out_dir,
            preset=args.preset,
            target_lufs=args.normalize_lufs,
            true_peak=args.true_peak,
            lra=args.lra,
            out_format=args.format,
            gain_db=args.gain_db,
            force=args.force,
            recursive=args.recursive,
            log=lambda m: print(m, flush=True),
        )
    except FxError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"Procesados: {result['processed']}")
    print(f"Salida: {result['output_dir']}")

    if result["failed"]:
        print(f"Fallidos: {len(result['failed'])}")
        for item in result["failed"][:20]:
            print(f"  {item['file']}: {item['error']}")
        if len(result["failed"]) > 20:
            print(f"  ... y {len(result['failed']) - 20} más.")
        return 1

    return 0


def cmd_fx_apply(args, data_dir, settings, store) -> int:
    src = Path(args.audio).expanduser()
    dest = (
        Path(args.out).expanduser()
        if args.out
        else src.with_name(f"{src.stem}_fx{src.suffix}")
    )

    try:
        out = apply_fx(
            src,
            dest,
            args.preset,
            gain_db=args.gain_db,
            force=args.force,
            target_lufs=args.normalize_lufs,
            true_peak=args.true_peak,
            lra=args.lra,
        )
    except FxError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Audio procesado: {out}")
    print()

    try:
        data = analyze_audio(out)
        print("Análisis de salida:")
        print(format_analysis(data))
    except FxError as exc:
        print(f"(advertencia: no se pudo analizar la salida: {exc})", file=sys.stderr)

    return 0


def cmd_model_download(args, data_dir, settings, store) -> int:
    from .engines.xtts import XttsEngine

    print("Se va a DESCARGAR el modelo XTTS-v2 (~1,8 GB) desde Internet.")
    print(
        "Licencia: Coqui Public Model License (con restricciones de uso comercial). "
        "Léela antes de aceptar."
    )
    if input("¿Continuar con la descarga? [s/N] ").strip().lower() not in ("s", "si", "sí"):
        print("Cancelado.")
        return 1
    engine = XttsEngine(threads=settings.threads, offline=False)
    engine.load()
    engine.unload()
    print("Modelo disponible. A partir de ahora VoxForge funciona sin conexión.")
    return 0


def cmd_cache_stats(args, data_dir, settings, store) -> int:
    """Muestra estadísticas de la caché."""
    from .cache_manager import CacheManager
    
    cache_manager = CacheManager(
        cache_dir=data_dir / "cache",
        store=store,
        voices_dir=data_dir / "voices",
        models_dir=data_dir / "models",
    )
    
    stats = cache_manager.get_stats()
    if NOVA_CLI:
        nova_print("Estadisticas de cache:", "accent")
        nova_print(f"  {stats}")
    else:
        print(f"Estadisticas de cache:")
        print(f"  {stats}")
    return 0


def cmd_cache_cleanup(args, data_dir, settings, store) -> int:
    """Limpia la caché según los parámetros proporcionados."""
    from .cache_manager import CacheManager
    import re
    
    cache_manager = CacheManager(
        cache_dir=data_dir / "cache",
        store=store,
        voices_dir=data_dir / "voices",
        models_dir=data_dir / "models",
    )
    
    # Parsear opciones
    dry_run = getattr(args, 'dry_run', False)
    
    # Si no se especifica nada, mostrar ayuda
    if not any([args.all, args.fragments, args.voices, args.models, args.older_than, args.max_size]):
        print("Debes especificar al menos una opcion de limpieza:")
        print("  --all              Limpiar todo")
        print("  --fragments        Limpiar solo fragmentos")
        print("  --voices          Limpiar solo voces")
        print("  --models          Limpiar solo modelos")
        print("  --older-than      Limpiar archivos mas antiguos que X (ej: '7d', '24h')")
        print("  --max-size        Limpiar hasta que el tamano sea menor que X (ej: '1GB')")
        return 1
    
    # Parsear --older-than
    older_than_days = None
    older_than_hours = None
    if args.older_than:
        match = re.match(r'^(\d+)([dh]?)$', args.older_than.lower())
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            if unit == 'd':
                older_than_days = value
            elif unit == 'h':
                older_than_hours = value
            else:  # Default to days
                older_than_days = value
        else:
            print(f"Formato invalido para --older-than: {args.older_than}")
            print("Formato valido: '7d' (7 dias), '24h' (24 horas), '30' (30 dias)")
            return 1
    
    # Parsear --max-size
    max_size_bytes = None
    if args.max_size:
        match = re.match(r'^(\d+(\.\d+)?)\s*(B|KB|MB|GB|TB)$', args.max_size.upper())
        if match:
            value = float(match.group(1))
            unit = match.group(3)
            multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
            max_size_bytes = int(value * multipliers[unit])
        else:
            print(f"Formato invalido para --max-size: {args.max_size}")
            print("Formato valido: '1GB', '500MB', '10GB'")
            return 1
    
    # Realizar la limpieza
    if args.all:
        result = cache_manager.cleanup_all(dry_run=dry_run)
    elif args.fragments and not (args.voices or args.models):
        if older_than_days or older_than_hours:
            result = cache_manager.cleanup_fragments(
                older_than_days=older_than_days,
                older_than_hours=older_than_hours,
                dry_run=dry_run
            )
        elif max_size_bytes:
            result = cache_manager.cleanup_by_size(
                max_size_bytes=max_size_bytes,
                fragments=True,
                voices=False,
                models=False,
                dry_run=dry_run
            )
        else:
            result = cache_manager.cleanup_fragments(all=True, dry_run=dry_run)
    elif args.voices and not (args.fragments or args.models):
        result = cache_manager.cleanup_voices(all=True, dry_run=dry_run)
    elif args.models and not (args.fragments or args.voices):
        if args.all:
            result = cache_manager._cleanup_all_models(dry_run=dry_run)
        else:
            print("Para limpiar modelos, usa --all o especifica --older-than")
            return 1
    elif older_than_days or older_than_hours:
        result = cache_manager.cleanup_by_age(
            days=older_than_days,
            hours=older_than_hours,
            fragments=args.fragments,
            voices=args.voices,
            models=args.models,
            dry_run=dry_run
        )
    elif max_size_bytes:
        result = cache_manager.cleanup_by_size(
            max_size_bytes=max_size_bytes,
            fragments=args.fragments,
            voices=args.voices,
            models=args.models,
            dry_run=dry_run
        )
    else:
        print("Opciones de limpieza ambiguas. Usa --all o especifica exactamente que limpiar.")
        return 1
    
    # Mostrar resultados
    if dry_run:
        print(f"[DRY RUN] {result}")
        print("Usa el comando sin --dry-run para ejecutar la limpieza.")
    else:
        print(f"Limpieza completada: {result}")
        if result.errors:
            print(f"\nAdvertencias:")
            for error in result.errors:
                print(f"  - {error}")
    
    return 0


def cmd_speak(args, data_dir, settings, store) -> int:
    from .engines.base import ModelUnavailableError
    from .engines.xtts import XttsEngine
    from .pipeline import narrate

    cfg, pron_langs = _load_pron_config(args, data_dir)

    profile = store.get_profile(args.voice)
    if profile is None:
        print(
            f"No existe el perfil '{args.voice}'. "
            "Perfiles: python -m voxforge voice list",
            file=sys.stderr,
        )
        return 2

    text_file = Path(args.text_file).expanduser()
    if not text_file.is_file():
        print(f"No existe el archivo de texto: {text_file}", file=sys.stderr)
        return 2

    if text_file.suffix.lower() in BINARY_IMPORT_EXTS:
        print(f"Extrayendo texto de {text_file.name}...")
        try:
            text = extract_text(
                text_file,
                lang=args.language or settings.language,
                log=print,
            )
        except ImporterError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    else:
        text = text_file.read_text(encoding="utf-8")

    text = _apply_pronunciation(text, cfg, pron_langs)

    if not text.strip():
        print("El archivo de texto está vacío.", file=sys.stderr)
        return 2

    final_out = (
        Path(args.out).expanduser()
        if args.out
        else data_dir / "exports" / f"{text_file.stem}_{args.voice}.wav"
    )

    use_fx = bool(getattr(args, "fx", None))
    narrate_out = final_out.with_name(final_out.stem + ".raw.wav") if use_fx else final_out

    engine = XttsEngine(threads=settings.threads)

    try:
        result = narrate(
            text,
            profile,
            engine,
            store,
            settings,
            data_dir / "cache",
            narrate_out,
            language=args.language,
            regen=args.regen,
        )
    except PauseError as exc:
        print(f"Error de marcas de pausa: {exc}", file=sys.stderr)
        return 1
    except ModelUnavailableError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(
            "\nInterrumpido. Los fragmentos ya generados quedan en caché: "
            "al repetir el comando se continúa."
        )
        return 130

    if use_fx:
        try:
            apply_fx(
                narrate_out,
                final_out,
                args.fx,
                gain_db=getattr(args, "fx_gain_db", 0.0),
                force=True,
            )
        except FxError as exc:
            print(
                f"Advertencia: audio generado en {narrate_out}, pero falló Voice FX: {exc}",
                file=sys.stderr,
            )
            return 1

        narrate_out.unlink(missing_ok=True)
        print(f"Voice FX aplicado: {args.fx} -> {final_out}")

    print(f"\nListo: {final_out if use_fx else result.out_path}")
    print(
        f"Fragmentos: {result.fragments} ({result.generated} generados, {result.cached} de caché, "
        f"{result.retried} con reintento, {result.doubtful} dudosos)"
    )
    if result.pauses:
        print(f"Pausas explícitas insertadas: {result.pauses}")
    print(
        f"Audio: {result.audio_s:.1f} s | Cálculo: {result.compute_s:.1f} s | "
        f"Pausas térmicas: {result.waited_s:.0f} s"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voxforge",
        description="VoxForge Local: voz clonada 100 % local",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="activar modo debug (logging detallado)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="modo silencioso (solo errores)",
    )
    parser.add_argument(
        "--nova",
        "--nova-theme",
        action="store_true",
        dest="nova_theme",
        help="activar tema NOVA cyberpunk (colores en terminal)",
    )
    parser.add_argument(
        "--theme",
        choices=["nova", "default"],
        default=None,
        help="seleccionar tema visual: 'nova' (cyberpunk) o 'default'",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="estado del sistema y de los datos").set_defaults(func=cmd_status)

    # ---- voice ----
    job = sub.add_parser("job", help="trabajos de producción en segundo plano")
    jsub = job.add_subparsers(dest="jcmd", required=True)

    jstart = jsub.add_parser(
        "start",
        help="lanzar un comando de voxforge como trabajo en segundo plano",
    )
    jstart.add_argument("--name", help="nombre descriptivo del trabajo")
    jstart.add_argument("--project", help="proyecto asociado; se intenta inferir si no se indica")
    jstart.add_argument("--ordinal", type=int, help="capítulo asociado; se intenta inferir si no se indica")
    jstart.add_argument(
        "--allow-duplicate",
        action="store_true",
        help="permitir varios trabajos activos del mismo proyecto/capítulo",
    )
    jstart.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="tras --, argumentos de voxforge sin escribir 'python -m voxforge'",
    )
    jstart.set_defaults(func=cmd_job_start)

    jrun = jsub.add_parser("run", help=argparse.SUPPRESS)
    jrun.add_argument("--id", type=int, required=True)
    jrun.add_argument("command", nargs=argparse.REMAINDER)
    jrun.set_defaults(func=cmd_job_run)

    jlist = jsub.add_parser("list", help="listar trabajos")
    jlist.add_argument("--limit", type=int, default=50)
    jlist.add_argument("--status", help="filtrar por estado")
    jlist.add_argument("--project", help="filtrar por proyecto")
    jlist.set_defaults(func=cmd_job_list)

    jshow = jsub.add_parser("show", help="ver detalle de un trabajo")
    jshow.add_argument("id", type=int)
    jshow.set_defaults(func=cmd_job_show)

    jlogs = jsub.add_parser("logs", help="mostrar las últimas líneas del log de un trabajo")
    jlogs.add_argument("id", type=int)
    jlogs.add_argument("--tail", type=int, default=80, help="número de líneas finales")
    jlogs.set_defaults(func=cmd_job_logs)

    jcancel = jsub.add_parser("cancel", help="cancelar un trabajo activo")
    jcancel.add_argument("id", type=int)
    jcancel.set_defaults(func=cmd_job_cancel)

    jcleanup = jsub.add_parser("cleanup", help="eliminar trabajos terminados y sus logs")
    jcleanup.add_argument("--days", type=float, default=7.0, help="eliminar terminados hace más de N días")
    jcleanup.add_argument("--all-finished", action="store_true", help="eliminar todos los terminados")
    jcleanup.set_defaults(func=cmd_job_cleanup)

    voice = sub.add_parser("voice", help="gestionar perfiles de voz")
    vsub = voice.add_subparsers(dest="vcmd", required=True)

    add = vsub.add_parser("add", help="crear un perfil a partir de una muestra")
    add.add_argument("name")
    add.add_argument("wav", help="muestra de referencia (WAV, FLAC, MP3...)")
    add.add_argument("--language", help="idioma del perfil (por defecto el de la configuración)")
    add.set_defaults(func=cmd_voice_add)

    check = vsub.add_parser("check", help="analizar la calidad de una muestra o de un perfil")
    check.add_argument("wav", nargs="?", help="archivo de audio a analizar")
    check.add_argument("--profile", help="analizar la muestra de un perfil existente")
    check.set_defaults(func=cmd_voice_check)

    record = vsub.add_parser("record", help="grabar una muestra desde el micrófono y analizarla")
    record.add_argument("name", help="nombre base del archivo de la toma")
    record.add_argument("--source", default="default", help="entrada de audio (por defecto la predeterminada)")
    record.add_argument("--skip-room-check", action="store_true", help="no medir el ruido de la sala antes")
    record.set_defaults(func=cmd_voice_record)

    prep = vsub.add_parser(
        "prepare",
        help="limpiar una muestra: ruido, recorte y nivel (no modifica el original)",
    )
    prep.add_argument("wav", nargs="?", help="archivo de audio a preparar")
    prep.add_argument("--profile", help="preparar la muestra de un perfil existente")
    prep.add_argument("--out", help="archivo de salida (por defecto data/samples/NOMBRE_limpia.wav)")
    prep.add_argument(
        "--nr",
        type=float,
        default=12.0,
        help="reducción de ruido en dB (0 = desactivada; por defecto 12)",
    )
    prep.add_argument("--force", action="store_true", help="sobrescribir la salida si ya existe")
    prep.set_defaults(func=cmd_voice_prepare)

    sim = vsub.add_parser(
        "similarity",
        help="comparar objetivamente el parecido de audios con una referencia",
    )
    sim.add_argument("ref", help="audio de referencia (p. ej. tu grabación original)")
    sim.add_argument("files", nargs="+", help="audios a comparar con la referencia")
    sim.add_argument(
        "--window",
        type=float,
        default=8.0,
        help="duración de cada ventana en segundos (por defecto 8)",
    )
    sim.set_defaults(func=cmd_voice_similarity)

    vsub.add_parser("list", help="listar perfiles").set_defaults(func=cmd_voice_list)

    delete = vsub.add_parser("delete", help="eliminar un perfil de voz y sus datos asociados")
    delete.add_argument("name", help="nombre exacto del perfil a eliminar")
    delete.add_argument(
        "--yes",
        action="store_true",
        help="ejecutar el borrado; sin esta opción solo se muestra el plan",
    )
    delete.add_argument(
        "--source",
        action="store_true",
        help="eliminar también la muestra fuente si existe en data/samples",
    )
    delete.add_argument(
        "--shred",
        action="store_true",
        help="sobrescribir archivos antes de borrarlos (mejor esfuerzo)",
    )
    delete.set_defaults(func=cmd_voice_delete)

    # ---- text ----
    textp = sub.add_parser("text", help="importar textos")
    tsub = textp.add_subparsers(dest="tcmd", required=True)

    ext = tsub.add_parser(
        "extract",
        help="extraer texto de TXT, MD, DOCX, EPUB o PDF (con OCR si está escaneado)",
    )
    ext.add_argument("file")
    ext.add_argument(
        "--lang",
        default="spa",
        help="idioma del OCR para PDF escaneado (spa, eng, por, fra...)",
    )
    ext.add_argument(
        "--out",
        help="archivo .txt de salida (por defecto data/imports/NOMBRE.txt)",
    )
    ext.set_defaults(func=cmd_text_extract)

    # ---- project ----
    project = sub.add_parser("project", help="gestionar proyectos de narración")
    psub = project.add_subparsers(dest="pcmd", required=True)

    pcreate = psub.add_parser("create", help="crear un proyecto con una voz asignada")
    pcreate.add_argument("name")
    pcreate.add_argument("--voice", required=True, help="perfil de voz del proyecto")
    pcreate.add_argument("--language", help="idioma (por defecto el de la configuración)")
    pcreate.set_defaults(func=cmd_project_create)

    psub.add_parser("list", help="listar proyectos").set_defaults(func=cmd_project_list)

    pshow = psub.add_parser("show", help="ver un proyecto")
    pshow.add_argument("name")
    pshow.set_defaults(func=cmd_project_show)

    pdel = psub.add_parser("delete", help="eliminar un proyecto y sus capítulos")
    pdel.add_argument("name")
    pdel.add_argument(
        "--yes",
        action="store_true",
        help="ejecutar el borrado; sin esta opción solo se muestra el plan",
    )
    pdel.set_defaults(func=cmd_project_delete)

    pimport = psub.add_parser(
        "import",
        help="importar un libro completo y crear capítulos por tamaño",
    )
    pimport.add_argument("name", help="nombre del proyecto")
    pimport.add_argument(
        "--file",
        required=True,
        help="archivo del libro (TXT, MD, DOCX, EPUB o PDF; OCR automático si está escaneado)",
    )
    pimport.add_argument("--voice", required=True, help="perfil de voz del proyecto")
    pimport.add_argument("--language", help="idioma del proyecto (por defecto el de la configuración)")
    pimport.add_argument(
        "--target-chars",
        type=int,
        default=DEFAULT_TARGET_CHARS,
        help=f"caracteres objetivo por capítulo (por defecto {DEFAULT_TARGET_CHARS})",
    )
    pimport.add_argument(
        "--hard-max-chars",
        type=int,
        default=DEFAULT_HARD_MAX_CHARS,
        help=f"máximo duro por capítulo (por defecto {DEFAULT_HARD_MAX_CHARS})",
    )
    pimport.add_argument(
        "--parts-dir",
        help="directorio donde guardar las partes extraídas (por defecto data/imports/PROYECTO_partes)",
    )
    pimport.add_argument(
        "--lang",
        default="spa",
        help="idioma del OCR para PDF escaneado (spa, eng, por, fra...)",
    )
    pimport.add_argument(
        "--replace",
        action="store_true",
        help="si el proyecto ya existe, eliminarlo y recrearlo",
    )
    pimport.set_defaults(func=cmd_project_import)



    # ---- chapter ----
    chapter = sub.add_parser("chapter", help="gestionar capítulos de un proyecto")
    csub = chapter.add_subparsers(dest="ccmd", required=True)

    cadd = csub.add_parser("add", help="importar un capítulo desde TXT/MD/DOCX/EPUB/PDF")
    cadd.add_argument("project")
    cadd.add_argument("title")
    cadd.add_argument("--file", required=True, help="archivo de origen (TXT, MD, DOCX, EPUB o PDF)")
    cadd.add_argument(
        "--lang",
        default="spa",
        help="idioma del OCR para PDF escaneado (spa, eng, por, fra...)",
    )
    cadd.set_defaults(func=cmd_chapter_add)

    clist = csub.add_parser("list", help="listar capítulos de un proyecto")
    clist.add_argument("project")
    clist.set_defaults(func=cmd_chapter_list)

    cnarr = csub.add_parser("narrate", help="narrar un capítulo del proyecto")
    cnarr.add_argument("project")
    cnarr.add_argument("ordinal", type=int, help="número de capítulo (ver chapter list)")
    cnarr.add_argument(
        "--out",
        help="archivo de salida (por defecto data/exports/PROYECTO/NNN_titulo.mp3)",
    )
    cnarr.add_argument("--language", help="idioma (por defecto el del proyecto)")
    cnarr.add_argument("--regen", action="store_true", help="ignorar caché y regenerar")
    _add_pron_args(cnarr)
    _add_fx_args(cnarr)
    cnarr.set_defaults(func=cmd_chapter_narrate)

    cpause = csub.add_parser("pauses", help="previsualizar pausas explícitas de un capítulo")
    cpause.add_argument("project")
    cpause.add_argument("ordinal", type=int, help="número de capítulo (ver chapter list)")
    _add_pron_args(cpause)
    cpause.set_defaults(func=cmd_chapter_pauses)

    cfrag = csub.add_parser("fragments", help="listar los fragmentos de un capítulo")
    cfrag.add_argument("project")
    cfrag.add_argument("ordinal", type=int, help="número de capítulo (ver chapter list)")
    _add_pron_args(cfrag)
    cfrag.set_defaults(func=cmd_chapter_fragments)

    cregen = csub.add_parser(
        "regen",
        help="regenerar un fragmento individual y reensamblar el capítulo exportado",
    )
    cregen.add_argument("project")
    cregen.add_argument("ordinal", type=int, help="número de capítulo")
    cregen.add_argument(
        "--fragment",
        type=int,
        required=True,
        help="número de fragmento a regenerar (ver chapter fragments)",
    )
    cregen.add_argument(
        "--seed",
        type=int,
        default=None,
        help="semilla fija para reproducir el take; sin ella se usa una aleatoria (se imprime por pantalla)",
    )
    cregen.add_argument(
        "--out",
        help="archivo de salida (por defecto data/exports/PROYECTO/NNN_titulo.mp3)",
    )
    cregen.add_argument("--language", help="idioma (por defecto el del proyecto)")
    _add_pron_args(cregen)
    _add_fx_args(cregen)
    cregen.set_defaults(func=cmd_chapter_regen)

    # ---- project-narrate ----
    proj_narr = sub.add_parser(
        "project-narrate",
        help="narrar todos los capítulos de un proyecto",
    )
    proj_narr.add_argument("project")
    proj_narr.add_argument(
        "--out-dir",
        help="directorio de salida (por defecto data/exports/PROYECTO/)",
    )
    proj_narr.add_argument(
        "--format",
        default="mp3",
        choices=["wav", "flac", "mp3", "ogg"],
        help="formato de exportación por capítulo (por defecto mp3)",
    )
    proj_narr.add_argument("--language", help="idioma (por defecto el del proyecto)")
    proj_narr.add_argument("--regen", action="store_true", help="ignorar caché y regenerar")
    _add_pron_args(proj_narr)
    _add_fx_args(proj_narr)
    proj_narr.set_defaults(func=cmd_project_narrate)

    # ---- pron ----
    pron = sub.add_parser("pron", help="diccionario de pronunciación")
    pronsub = pron.add_subparsers(dest="prcmd", required=True)

    ppacks = pronsub.add_parser("packs", help="listar packs de pronunciación disponibles")
    _add_pron_args(ppacks)
    ppacks.set_defaults(func=cmd_pron_packs)

    pcheck = pronsub.add_parser("check", help="mostrar qué sustituiría el diccionario")
    pcheck.add_argument(
        "file",
        nargs="?",
        help="archivo TXT/MD/PDF; opcional si usas --project y --chapter",
    )
    pcheck.add_argument("--project", help="proyecto del capítulo a comprobar")
    pcheck.add_argument("--chapter", type=int, help="ordinal del capítulo a comprobar")
    pcheck.add_argument("--lang", default="spa", help="idioma OCR si el archivo es PDF")
    _add_pron_args(pcheck)
    pcheck.set_defaults(func=cmd_pron_check)

    paidit = pronsub.add_parser(
        "audit",
        help="listar nombres propios probables y marcar los no cubiertos por el diccionario",
    )
    paidit.add_argument(
        "file",
        nargs="?",
        help="archivo TXT/MD/PDF; opcional con --project/--chapter",
    )
    paidit.add_argument("--project", help="proyecto del capítulo a auditar")
    paidit.add_argument("--chapter", type=int, help="ordinal del capítulo a auditar")
    paidit.add_argument("--lang", default="spa", help="idioma OCR si el archivo es PDF")
    paidit.add_argument("--top", type=int, default=80, help="nº máximo de candidatos a mostrar")
    _add_pron_args(paidit)
    paidit.set_defaults(func=cmd_pron_audit)

    fx = sub.add_parser("fx", help="post-proceso de audio (ecualización, compresión, limitador)")
    fsub = fx.add_subparsers(dest="fxcmd", required=True)

    fsub.add_parser("presets", help="listar presets de Voice FX").set_defaults(
        func=cmd_fx_presets
    )

    fan = fsub.add_parser("analyze", help="analizar LUFS/pico/rango con ffmpeg")
    fan.add_argument("audio", help="archivo de audio a analizar")
    fan.set_defaults(func=cmd_fx_analyze)

    fnorm = fsub.add_parser(
        "normalize",
        help="normalizar LUFS con loudnorm en dos pasadas",
    )
    fnorm.add_argument("audio", help="archivo de audio de entrada")
    fnorm.add_argument("--out", help="archivo de salida (por defecto NOMBRE_normalized.EXT)")
    fnorm.add_argument(
        "--target-lufs",
        type=float,
        default=-16.0,
        help="LUFS integrado objetivo (por defecto -16)",
    )
    fnorm.add_argument(
        "--true-peak",
        type=float,
        default=-1.5,
        help="pico verdadero objetivo en dBTP (por defecto -1.5)",
    )
    fnorm.add_argument(
        "--lra",
        type=float,
        default=11.0,
        help="rango dinámico objetivo en LU (por defecto 11)",
    )
    fnorm.add_argument(
        "--force",
        action="store_true",
        help="sobrescribir la salida si ya existe",
    )
    fnorm.set_defaults(func=cmd_fx_normalize)

    fbatch = fsub.add_parser(
        "batch",
        help="procesar por lotes un directorio de audios (preset y/o normalización LUFS)",
    )
    fbatch.add_argument("dir", help="directorio de entrada con archivos de audio")
    fbatch.add_argument(
        "--out-dir",
        help="directorio de salida (por defecto ENTRADA/processed)",
    )
    fbatch.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        help="preset de Voice FX",
    )
    fbatch.add_argument(
        "--normalize-lufs",
        type=float,
        default=None,
        help="normalizar a este LUFS integrado (p. ej. -16)",
    )
    fbatch.add_argument(
        "--true-peak",
        type=float,
        default=-1.5,
        help="pico verdadero objetivo en dBTP (por defecto -1.5)",
    )
    fbatch.add_argument(
        "--lra",
        type=float,
        default=11.0,
        help="rango dinámico objetivo en LU (por defecto 11)",
    )
    fbatch.add_argument(
        "--format",
        choices=["wav", "flac", "mp3", "ogg"],
        help="formato de salida; por defecto mantiene el de entrada",
    )
    fbatch.add_argument(
        "--gain-db",
        type=float,
        default=0.0,
        help="ganancia aplicada antes del preset",
    )
    fbatch.add_argument(
        "--force",
        action="store_true",
        help="sobrescribir salidas existentes",
    )
    fbatch.add_argument(
        "--recursive",
        action="store_true",
        help="buscar archivos en subdirectorios",
    )
    fbatch.set_defaults(func=cmd_fx_batch)

    fapp = fsub.add_parser("apply", help="aplicar un preset a un archivo exportado")
    fapp.add_argument("audio", help="archivo de audio de entrada")
    fapp.add_argument(
        "--preset",
        required=True,
        choices=sorted(PRESETS),
        help="preset de post-proceso",
    )
    fapp.add_argument(
        "--out",
        help="archivo de salida (por defecto NOMBRE_fx.EXT)",
    )
    fapp.add_argument(
        "--gain-db",
        type=float,
        default=0.0,
        help="ajuste final de ganancia en dB",
    )
    fapp.add_argument(
        "--normalize-lufs",
        type=float,
        default=None,
        help="tras el preset, normalizar a este LUFS integrado (p. ej. -16)",
    )
    fapp.add_argument(
        "--true-peak",
        type=float,
        default=-1.5,
        help="pico verdadero objetivo en dBTP al normalizar (por defecto -1.5)",
    )
    fapp.add_argument(
        "--lra",
        type=float,
        default=11.0,
        help="rango dinámico objetivo en LU al normalizar (por defecto 11)",
    )
    fapp.add_argument(
        "--force",
        action="store_true",
        help="sobrescribir la salida si ya existe",
    )
    fapp.set_defaults(func=cmd_fx_apply)

    model = sub.add_parser("model", help="gestionar modelos de voz")
    msub = model.add_subparsers(dest="mcmd", required=True)
    msub.add_parser(
        "download",
        help="descargar XTTS-v2 (única operación que usa Internet)",
    ).set_defaults(func=cmd_model_download)

    # ---- cache ---
    cache = sub.add_parser("cache", help="gestionar la cache")
    csub = cache.add_subparsers(dest="ccmd", required=True)
    
    # cache stats
    csub.add_parser(
        "stats",
        help="mostrar estadisticas de la cache",
    ).set_defaults(func=cmd_cache_stats)
    
    # cache cleanup
    cleanup = csub.add_parser("cleanup", help="limpiar la cache")
    cleanup.add_argument(
        "--all",
        action="store_true",
        help="limpiar todo (fragmentos, voces, modelos)",
    )
    cleanup.add_argument(
        "--fragments",
        action="store_true",
        help="limpiar solo fragmentos",
    )
    cleanup.add_argument(
        "--voices",
        action="store_true",
        help="limpiar solo voces",
    )
    cleanup.add_argument(
        "--models",
        action="store_true",
        help="limpiar solo modelos",
    )
    cleanup.add_argument(
        "--older-than",
        type=str,
        metavar="DURATION",
        help="limpiar archivos mas antiguos que DURATION (ej: 7d, 24h, 30d)",
    )
    cleanup.add_argument(
        "--max-size",
        type=str,
        metavar="SIZE",
        help="limpiar hasta que el tamano sea menor que SIZE (ej: 1GB, 500MB, 10GB)",
    )
    cleanup.add_argument(
        "--dry-run",
        action="store_true",
        help="mostrar que se eliminaria sin hacerlo",
    )
    cleanup.set_defaults(func=cmd_cache_cleanup)

    # ---- speak ----
    speak = sub.add_parser("speak", help="narrar un archivo de texto con una voz")
    speak.add_argument("text_file")
    speak.add_argument("--voice", required=True, help="nombre del perfil")
    speak.add_argument("--out", help="archivo de salida (.wav, .flac, .mp3 u .ogg)")
    speak.add_argument("--language", help="idioma (por defecto el del perfil)")
    speak.add_argument(
        "--regen",
        action="store_true",
        help="regenerar todos los fragmentos con una semilla nueva (ignora la caché)",
    )
    _add_pron_args(speak)
    _add_fx_args(speak)
    speak.set_defaults(func=cmd_speak)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    
    # Configurar tema NOVA para salida en terminal si está solicitado
    use_nova_cli = getattr(args, 'nova_theme', False) or (getattr(args, 'theme', None) == 'nova')
    global NOVA_CLI  # Hacer accesible globalmente
    NOVA_CLI = None
    
    if use_nova_cli:
        try:
            from voxforge.themes import NOVA_CLI_Theme
            NOVA_CLI = NOVA_CLI_Theme
        except ImportError:
            # Si el módulo no está disponible, no usar tema
            pass
    
    # Configurar logging basado en flags
    if getattr(args, 'debug', False):
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(__name__)
        logger.debug("Modo debug activado")
    elif getattr(args, 'quiet', False):
        import logging
        logging.basicConfig(level=logging.WARNING)
    
    data_dir = home()
    settings = load_settings(data_dir)
    store = Store(data_dir / "voxforge.db")
    try:
        return args.func(args, data_dir, settings, store)
    except sqlite3.Error as exc:
        if NOVA_CLI:
            print(f"{NOVA_CLI.error('✗ Error de base de datos:')} {exc}", file=sys.stderr)
        else:
            print(f"Error de base de datos: {exc}", file=sys.stderr)
        return 1
    finally:
        store.close()
