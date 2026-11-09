"""Guardia térmica: lee la temperatura de la CPU y pausa el trabajo si se calienta."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

_BASE = Path("/sys/class/thermal")


def cpu_temp_c() -> float | None:
    """Temperatura del paquete de la CPU (sensor x86_pkg_temp); si no existe, la mayor de todas."""
    pkg = None
    readings: list[float] = []
    for zone in sorted(_BASE.glob("thermal_zone*")):
        try:
            value = int((zone / "temp").read_text()) / 1000
            kind = (zone / "type").read_text().strip()
        except (OSError, ValueError):
            continue
        readings.append(value)
        if kind == "x86_pkg_temp":
            pkg = value
    if pkg is not None:
        return pkg
    return max(readings) if readings else None


def wait_if_hot(
    pause_c: float,
    resume_c: float,
    log: Callable[[str], None] = print,
    poll_s: float = 5.0,
    read: Callable[[], float | None] = cpu_temp_c,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    """Si la CPU supera pause_c, espera hasta que baje de resume_c. Devuelve segundos esperados."""
    temp = read()
    if temp is None or temp < pause_c:
        return 0.0
    log(f"  CPU a {temp:.0f} °C: pausa para enfriar hasta {resume_c:.0f} °C...")
    waited = 0.0
    while temp is not None and temp > resume_c:
        sleep(poll_s)
        waited += poll_s
        temp = read()
    return waited
