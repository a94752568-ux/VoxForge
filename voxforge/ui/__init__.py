"""Paquete de UI estilo Night City para VoxForge.

Módulos:
- theme: Paleta de colores y QSS cyberpunk.
- widgets: Widgets personalizados (NeonProgressBar, PulseChip, WaveformWidget,
  FragmentCard, CyberPanel).
- main_window: Ventana principal con layout de 3 columnas.

Uso rápido:
    from voxforge.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

Integración con tu motor real:
    1. Conecta las señales de tus botones (btn_import, btn_play, etc.)
       a tus funciones existentes.
    2. Reemplaza los QListWidget de demostración por tus listas reales.
    3. Conecta NeonProgressBar a tu progreso de trabajo real.
    4. Dos puntos TODO marcados en main_window.py para enchufar el motor.
"""

from .theme import QSS, PALETTE  # noqa: F401
from .widgets import (  # noqa: F401
    NeonProgressBar,
    PulseChip,
    WaveformWidget,
    FragmentCard,
    CyberPanel,
    apply_glow,
)
from .main_window import MainWindow  # noqa: F401

__all__ = [
    "QSS",
    "PALETTE",
    "NeonProgressBar",
    "PulseChip",
    "WaveformWidget",
    "FragmentCard",
    "CyberPanel",
    "apply_glow",
    "MainWindow",
]
