"""Análisis de calidad de una muestra de voz (solo numpy: sin dependencias nuevas).

Los umbrales son provisionales: se afinarán con muestras reales.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FRAME_S = 0.02            # ventanas de 20 ms
FLOOR_DB = -90.0          # evita valores absurdos con silencio digital


@dataclass
class Check:
    name: str
    value: str
    status: str           # "OK" | "AVISO" | "MAL"
    advice: str = ""


def _frame_db(audio: np.ndarray, sr: int) -> np.ndarray:
    size = max(int(sr * FRAME_S), 1)
    n = len(audio) // size
    if n == 0:
        return np.array([FLOOR_DB])
    frames = audio[: n * size].reshape(n, size)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    return np.maximum(20 * np.log10(rms + 1e-12), FLOOR_DB)


def _runs(mask: np.ndarray) -> list[int]:
    """Longitudes de las rachas consecutivas de True."""
    out, count = [], 0
    for value in mask:
        if value:
            count += 1
        elif count:
            out.append(count)
            count = 0
    if count:
        out.append(count)
    return out


def analyze(audio: np.ndarray, sr: int) -> list[Check]:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    duration = len(audio) / sr
    checks: list[Check] = []

    # Duración
    if duration < 6:
        st, adv = "MAL", "Demasiado corta: graba entre 10 y 30 s."
    elif duration < 10:
        st, adv = "AVISO", "Corta: lo ideal son 10-30 s."
    elif duration <= 30:
        st, adv = "OK", ""
    else:
        st, adv = "AVISO", "Más de 30 s no suele mejorar el clon: usa el mejor tramo."
    checks.append(Check("Duración", f"{duration:.1f} s", st, adv))

    # Nivel y recorte
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    peak_db = 20 * np.log10(peak + 1e-12)
    if peak_db < -60:
        checks.append(Check("Señal", f"{peak_db:.0f} dBFS", "MAL",
                            "No hay señal de audio: comprueba que el micrófono no esté silenciado "
                            "y que la entrada seleccionada sea la correcta."))
        return checks
    if peak_db > -0.5:
        st, adv = "AVISO", "Nivel casi al máximo: baja la ganancia del micrófono."
    elif peak_db < -24:
        st, adv = "AVISO", "Nivel muy bajo: acércate al micrófono o sube la ganancia."
    else:
        st, adv = "OK", ""
    checks.append(Check("Nivel de pico", f"{peak_db:.1f} dBFS", st, adv))

    clipped = float(np.mean(np.abs(audio) >= 0.999)) * 100 if len(audio) else 0.0
    if clipped > 0.1:
        st, adv = "MAL", "Hay recortes (distorsión): vuelve a grabar con menos ganancia."
    elif clipped > 0.01:
        st, adv = "AVISO", "Algún recorte puntual."
    else:
        st, adv = "OK", ""
    checks.append(Check("Recorte", f"{clipped:.3f} %", st, adv))

    # Ruido de fondo y relación señal/ruido
    db = _frame_db(audio, sr)
    noise = float(np.percentile(db, 10))
    speech = float(np.percentile(db, 90))
    snr = speech - noise
    checks.append(Check("Ruido de fondo", f"{noise:.0f} dBFS", "OK"))
    if snr < 20:
        st, adv = "MAL", "Mucho ruido frente a la voz: graba en un lugar más silencioso."
    elif snr < 30:
        st, adv = "AVISO", "Algo de ruido: apaga ventiladores y graba en una sala silenciosa."
    else:
        st, adv = "OK", ""
    checks.append(Check("Relación señal/ruido", f"{snr:.0f} dB", st, adv))

    # Habla activa, pausas largas y silencios en los extremos
    if snr < 12:  # con tanto ruido no se puede separar la voz del fondo: evitamos avisos engañosos
        for name in ("Habla activa", "Pausa más larga", "Silencio en los extremos"):
            checks.append(Check(name, "n/d", "OK"))
        return checks
    active = db > noise + 10
    ratio = float(active.mean()) * 100
    checks.append(Check("Habla activa", f"{ratio:.0f} %", "OK" if ratio >= 35 else "AVISO",
                        "" if ratio >= 35 else "Hay demasiado silencio: lee de forma más continua."))
    if active.any():
        first, last = int(np.argmax(active)), len(active) - 1 - int(np.argmax(active[::-1]))
        inner = ~active[first:last + 1]
        longest = max(_runs(inner), default=0) * FRAME_S
        edges = max(first, len(active) - 1 - last) * FRAME_S
    else:
        longest = edges = duration
    checks.append(Check("Pausa más larga", f"{longest:.1f} s", "OK" if longest <= 1.5 else "AVISO",
                        "" if longest <= 1.5 else "Pausas largas dentro de la muestra: recórtalas."))
    checks.append(Check("Silencio en los extremos", f"{edges:.1f} s", "OK" if edges <= 1.0 else "AVISO",
                        "" if edges <= 1.0 else "Recorta el silencio del principio y del final."))
    return checks


def verdict(checks: list[Check]) -> str:
    if any(c.status == "MAL" for c in checks):
        return "No recomendable como referencia: corrige los puntos marcados como MAL."
    if any(c.status == "AVISO" for c in checks):
        return "Utilizable, con margen de mejora (ver avisos)."
    return "Muestra adecuada como referencia."


def format_report(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        lines.append(f"  {c.name:<26}{c.value:<12}{c.status}" + (f"  -> {c.advice}" if c.advice else ""))
    lines.append(f"Veredicto: {verdict(checks)}")
    return "\n".join(lines)


def room_noise(audio: np.ndarray) -> Check:
    """Valora unos segundos de silencio grabados antes de la toma (umbrales provisionales)."""
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    rms_db = 20 * np.log10(float(np.sqrt(np.mean(audio ** 2))) + 1e-12) if len(audio) else FLOOR_DB
    value = f"{rms_db:.0f} dBFS"
    if rms_db < -75:
        return Check("Ruido de la sala", value, "MAL",
                     "No llega señal: comprueba que el micrófono no esté silenciado ni sea otra entrada.")
    if rms_db <= -55:
        return Check("Ruido de la sala", value, "OK")
    if rms_db <= -45:
        return Check("Ruido de la sala", value, "AVISO",
                     "Hay algo de ruido: apaga ventiladores, ventanas abiertas o aparatos cercanos.")
    return Check("Ruido de la sala", value, "MAL",
                 "Ambiente muy ruidoso: busca una sala más silenciosa o acércate más al micrófono.")
