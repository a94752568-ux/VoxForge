#!/usr/bin/env python3
"""Runner de calibración XTTS-v2 (QF-2).

Genera audio frase × config, mide métricas de cola y escribe score_sheet.csv.

Uso:
    python scripts/calibrate_xtts.py --fase 2        # solo fase 2
    python scripts/calibrate_xtts.py --fase all      # todas las fases
    python scripts/calibrate_xtts.py --fase 1,2,3    # fases específicas
"""

from __future__ import annotations

import argparse
import csv
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

# Permitir importar voxforge desde el directorio raíz del proyecto
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voxforge.engines.xtts import XttsEngine  # noqa: E402


def cargar_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def adaptar_manifest(manifest_usuario: dict) -> dict:
    """Normaliza el manifest del usuario al formato interno del runner.

    El usuario escribe con claves como 'casos_prueba', 'calibracion_umbrales',
    'config_baseline'. Esta función las mapea a las claves internas que el
    runner consume: 'seed', 'model_version', 'reference_wav', 'language',
    'thresholds', 'frases'.
    """
    casos = manifest_usuario.get("casos_prueba", [])
    umbrales = manifest_usuario.get("calibracion_umbrales", {})

    # reference_wav: del primer caso que tenga ruta, o fallback por defecto
    ref_wav = "muestras/mi_voz_ref.wav"
    for c in casos:
        r = c.get("ruta_audio_referencia")
        if r and r != "null":
            ref_wav = r
            break

    # Umbrales: del usuario o defaults
    rms_max = umbrales.get("rms_cola_max", 0.02)
    dur_min = umbrales.get("dur_ratio_min", 0.85)
    dur_max = umbrales.get("dur_ratio_max", 1.20)

    return {
        "seed": manifest_usuario.get("seed", 42),
        "model_version": manifest_usuario.get(
            "model_version", "tts_models/multilingual/multi-dataset/xtts_v2"
        ),
        "reference_wav": ref_wav,
        "language": manifest_usuario.get("language", "es"),
        "thresholds": {
            "rms_cola_max": rms_max,
            "dur_ratio_min": dur_min,
            "dur_ratio_max": dur_max,
        },
        "frases": [
            {"id": c.get("id", f"frase_{i}"), "texto": c.get("texto_original", "")}
            for i, c in enumerate(casos)
        ],
    }


def rms_cola(wav: np.ndarray, sr: int, segundos: float = 0.2) -> float:
    """RMS de los últimos `segundos` segundos del audio."""
    n = int(sr * segundos)
    if n <= 0 or len(wav) == 0:
        return 0.0
    cola = wav[-n:]
    return float(np.sqrt(np.mean(cola ** 2)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibración de parámetros XTTS-v2")
    parser.add_argument(
        "--fase",
        required=True,
        help="Fase(s) a ejecutar: 1, 2, 3, 4 o 'all' (ej: --fase 2 o --fase 1,2)",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    testdata = base / "testdata" / "diccion"
    calib = base / "calib"
    calib_out = calib / "out"
    calib_out.mkdir(parents=True, exist_ok=True)
    calib.mkdir(parents=True, exist_ok=True)

    manifest_usuario = cargar_json(testdata / "manifest.json")
    manifest = adaptar_manifest(manifest_usuario)
    grid = cargar_json(testdata / "grid.json")

    seed = manifest["seed"]
    model_version = manifest["model_version"]
    reference_wav = (base / manifest["reference_wav"]).resolve()
    language = manifest["language"]
    thresholds = manifest["thresholds"]
    rms_max = thresholds["rms_cola_max"]
    dur_min = thresholds["dur_ratio_min"]
    dur_max = thresholds["dur_ratio_max"]

    frases = manifest["frases"]
    if not frases:
        print("ERROR: manifest.json no tiene frases. Llena testdata/diccion/manifest.json primero.")
        sys.exit(1)

    # Parsear fases solicitadas
    if args.fase == "all":
        fases_solicitadas = sorted({f["fase"] for f in grid["fases"]})
    else:
        try:
            fases_solicitadas = sorted({int(x.strip()) for x in args.fase.split(",")})
        except ValueError:
            print("ERROR: --fase debe ser 'all' o una lista como 1,2,3")
            sys.exit(1)

    fases = {f["fase"]: f for f in grid["fases"]}
    faltantes = [f for f in fases_solicitadas if f not in fases]
    if faltantes:
        print(f"ERROR: fases {faltantes} no existen en grid.json")
        sys.exit(1)

    # cps_baseline = chars por segundo del baseline (fase 1, config base)
    # Se usa para calcular dur_ratio: dur_real / dur_esperada
    cps_baseline = None

    # Columnas del score sheet
    csv_path = calib / "score_sheet.csv"
    csv_fields = [
        "frase_id",
        "frase_texto",
        "chars",
        "config_id",
        "length_penalty",
        "temperature",
        "repetition_penalty",
        "rms_cola",
        "cola_ok",
        "dur_real_s",
        "dur_esperada_s",
        "dur_ratio",
        "dur_ratio_ok",
        "seg_gen",
        "ram_mb",
        "nota_oido",
    ]

    # Abrir CSV en modo append (una fila por frase×config)
    with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_fields)
        writer.writeheader()

        for fase_num in fases_solicitadas:
            fase = fases[fase_num]
            print(f"\n=== FASE {fase_num}: {fase['nombre']} ===")

            for config in fase["configs"]:
                config_id = config["config_id"]
                gen_params = {
                    k: v for k, v in config.items() if k not in ("config_id",)
                }
                out_dir = calib_out / config_id
                out_dir.mkdir(parents=True, exist_ok=True)

                print(f"  Config {config_id}: {gen_params}")

                for frase in frases:
                    frase_id = frase["id"]
                    texto = frase["texto"]
                    chars = len(texto)

                    # --- Generación con medición de tiempo y RAM ---
                    tracemalloc_start = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    t0 = time.perf_counter()

                    engine = XttsEngine(threads=4, offline=True)
                    engine.load()
                    try:
                        wav = engine.synthesize(
                            texto,
                            reference_wav,
                            language,
                            seed,
                            **gen_params,
                        )
                    finally:
                        engine.unload()

                    seg_gen = time.perf_counter() - t0
                    tracemalloc_end = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    ram_mb = tracemalloc_end / 1024.0  # ru_maxrss en KB en Linux

                    # --- Guardar audio ---
                    out_wav = out_dir / f"{frase_id}.wav"
                    sf.write(out_wav, wav, engine.sample_rate)

                    # --- Métricas de cola ---
                    sr = engine.sample_rate
                    rms = rms_cola(wav, sr)
                    cola_ok = rms <= rms_max

                    dur_real = len(wav) / sr

                    # Duración esperada: chars / cps_baseline
                    # cps_baseline se calcula del baseline (fase 1, config base)
                    # si aún no se conoce, usar rate_min_cps del config del proyecto
                    if cps_baseline is None:
                        # Usar rate_min_cps del config.json del proyecto como referencia
                        proj_config = cargar_json(base / "data" / "config.json")
                        cps_baseline = proj_config.get("rate_min_cps", 6.0)
                    dur_esperada = chars / cps_baseline
                    dur_ratio = dur_real / dur_esperada if dur_esperada > 0 else 0.0
                    dur_ratio_ok = dur_min <= dur_ratio <= dur_max

                    # Si es el baseline, establecer cps_baseline real desde este audio
                    if config_id == "base" and fase_num == 1:
                        cps_baseline = chars / dur_real if dur_real > 0 else cps_baseline
                        # Recalcular dur_ratio con el cps real
                        dur_esperada = chars / cps_baseline
                        dur_ratio = dur_real / dur_esperada if dur_esperada > 0 else 0.0
                        dur_ratio_ok = dur_min <= dur_ratio <= dur_max

                    writer.writerow({
                        "frase_id": frase_id,
                        "frase_texto": texto[:60],
                        "chars": chars,
                        "config_id": config_id,
                        "length_penalty": gen_params.get("length_penalty", ""),
                        "temperature": gen_params.get("temperature", ""),
                        "repetition_penalty": gen_params.get("repetition_penalty", ""),
                        "rms_cola": round(rms, 6),
                        "cola_ok": cola_ok,
                        "dur_real_s": round(dur_real, 3),
                        "dur_esperada_s": round(dur_esperada, 3),
                        "dur_ratio": round(dur_ratio, 3),
                        "dur_ratio_ok": dur_ratio_ok,
                        "seg_gen": round(seg_gen, 2),
                        "ram_mb": round(ram_mb, 1),
                        "nota_oido": "",
                    })
                    print(
                        f"    {frase_id}: rms={rms:.4f} cola_ok={cola_ok} "
                        f"dur_ratio={dur_ratio:.2f} seg_gen={seg_gen:.1f}s ram={ram_mb:.0f}MB"
                    )

    print(f"\nScore sheet escrito en: {csv_path}")
    print(f"Audios en: {calib_out}")
    print("\nSiguiente paso: Alberto llena nota_oido (1-5) y entrega el veredicto de las dos hipótesis.")


if __name__ == "__main__":
    main()
