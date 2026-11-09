"""
theme.py — Paleta y QSS «Night City» para VoxForge.

Estilo cyberpunk: fondo profundo #05060F, paneles #0B0F22 / #0D1226,
acento cian #00F0FF, magenta #FF2A6D, morado #B967FF, ámbar #FFB000,
verde #00FF9C, texto #D6E6FF, tenue #7A8DB5.

Solo PySide6 + stdlib. Sin dependencias externas. 100% offline.
"""

from __future__ import annotations

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PALETA CYBERPUNK / NIGHT CITY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BG = "#05060F"          # Fondo principal (casi negro azulado)
PANEL = "#0B0F22"       # Paneles principales
PANEL_2 = "#0D1226"     # Paneles secundarios (ligeramente más claros)
PANEL_3 = "#151B33"     # Tarjetas / contenedores internos

CYAN = "#00F0FF"        # Acento principal cian neón
MAGENTA = "#FF2A6D"     # Acento secundario magenta
PURPLE = "#B967FF"      # Morado neón
AMBER = "#FFB000"       # Ámbar / advertencia
GREEN = "#00FF9C"       # Verde éxito / activo
TEXT = "#D6E6FF"        # Texto principal
MUTED = "#7A8DB5"       # Texto tenue / secundario
DARK = "#02040A"        # Sombras profundas

# Colores de estado
STATUS_OK = GREEN
STATUS_WARN = AMBER
STATUS_ERROR = MAGENTA
STATUS_IDLE = MUTED

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# QSS — Estilos Night City
# Se usan placeholders __CYAN__, __MAGENTA__, etc. que se reemplazan con .replace()
# para evitar problemas de f-string con llaves CSS.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_QSS_TEMPLATE = r"""
/* =========================================================================
   BASE
   ========================================================================= */
QMainWindow {{
    background: __BG__;
}}
QWidget {{
    background: transparent;
    color: __TEXT__;
    font-size: 12px;
    font-family: "Segoe UI", "Arial", sans-serif;
}}
QToolTip {{
    background: __PANEL_3__;
    color: __TEXT__;
    border: 1px solid __CYAN__;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11px;
}}

/* =========================================================================
   PANELES Y CONTENEDORES
   ========================================================================= */
QFrame#cyberPanel {{
    background: __PANEL__;
    border: 1px solid __PURPLE__;
    border-radius: 10px;
}}

QFrame#panel2 {{
    background: __PANEL_2__;
    border: 1px solid #1E2438;
    border-radius: 8px;
}}

QFrame#card {{
    background: __PANEL_3__;
    border: 1px solid #1E2438;
    border-radius: 8px;
}}

QFrame#card:hover {{
    border-color: __CYAN__;
}}

QFrame#sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 __PANEL__, stop:1 __PANEL_2__);
    border-right: 1px solid #1E2438;
}}

/* =========================================================================
   BOTONES
   ========================================================================= */
QPushButton {{
    background: __PANEL_3__;
    color: __TEXT__;
    border: 1px solid __CYAN__;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 700;
    font-size: 12px;
}}

QPushButton:hover {{
    background: __CYAN__;
    color: #02040A;
    border-color: __CYAN__;
}}

QPushButton:pressed {{
    background: #8FF7E6;
}}

QPushButton:disabled {{
    background: #101528;
    color: #4A5A7A;
    border-color: #1E2438;
}}

QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 __CYAN__, stop:1 __MAGENTA__);
    color: #02040A;
    border: none;
    font-weight: 800;
}}

QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #8FF7E6, stop:1 #FF6AA3);
}}

QPushButton#danger {{
    background: rgba(255, 42, 109, 0.15);
    border: 1px solid __MAGENTA__;
    color: __MAGENTA__;
}}

QPushButton#danger:hover {{
    background: __MAGENTA__;
    color: #02040A;
}}

QPushButton#ghost {{
    background: transparent;
    border: 1px solid transparent;
    color: __MUTED__;
    padding: 5px 12px;
}}

QPushButton#ghost:hover {{
    background: __PANEL_3__;
    color: __TEXT__;
    border-color: __CYAN__;
}}

/* =========================================================================
   ETIQUETAS
   ========================================================================= */
QLabel {{
    color: __TEXT__;
}}

QLabel#title {{
    font-size: 20px;
    font-weight: 800;
    color: __CYAN__;
    letter-spacing: 1px;
}}

QLabel#subtitle {{
    color: __MUTED__;
    font-size: 11px;
}}

QLabel#eyebrow {{
    color: __PURPLE__;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
}}

/* =========================================================================
   LISTAS Y TARJETAS
   ========================================================================= */
QListWidget {{
    background: transparent;
    border: none;
    padding: 0;
    outline: none;
}}

QListWidget::item {{
    background: transparent;
    border: none;
    padding: 8px 12px;
    border-bottom: 1px solid #1E2438;
    margin: 2px 0;
    border-radius: 6px;
}}

QListWidget::item:hover {{
    background: #1E2A3A;
    border-color: __CYAN__;
}}

QListWidget::item:selected {{
    background: __PURPLE__;
    color: #02040A;
    border-color: __PURPLE__;
}}

QListWidget::item:selected:hover {{
    background: #D25CFF;
}}

/* =========================================================================
   BARRAS DE PROGRESO
   ========================================================================= */
QProgressBar {{
    background: #101528;
    border: 1px solid #1E2438;
    border-radius: 7px;
    text-align: center;
    color: __TEXT__;
    font-weight: 800;
    font-size: 10px;
    min-height: 18px;
    max-height: 18px;
}}

QProgressBar::chunk {{
    border-radius: 6px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 __CYAN__, stop:0.5 __PURPLE__, stop:1 __MAGENTA__);
}}

NeonProgressBar {{
    background: #101528;
    border: 1px solid #1E2438;
    border-radius: 7px;
    text-align: center;
    color: __TEXT__;
    font-weight: 800;
    font-size: 10px;
    min-height: 20px;
    max-height: 20px;
}}

NeonProgressBar::chunk {{
    border-radius: 6px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 __CYAN__, stop:0.45 __PURPLE__, stop:1 __MAGENTA__);
}}

/* =========================================================================
   SLIDERS
   ========================================================================= */
QSlider::groove:horizontal {{
    height: 5px;
    background: #1A2842;
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 __CYAN__, stop:1 #FF2A6D);
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: #EAFcFF;
    border: 1px solid __CYAN__;
}}

QSlider::handle:horizontal:hover {{
    background: #FFFFFF;
}}

/* =========================================================================
   CAMPOS DE TEXTO
   ========================================================================= */
QLineEdit, QComboBox, QSpinBox {{
    background: #0A1322;
    border: 1px solid #1E2438;
    border-radius: 8px;
    padding: 7px 12px;
    color: __TEXT__;
    selection-background-color: __CYAN__;
    selection-color: #02040A;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: __CYAN__;
}}

/* =========================================================================
   CHECKBOX
   ========================================================================= */
QCheckBox {{
    color: __MUTED__;
    spacing: 8px;
    font-size: 11px;
}}

QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid #2A4D7E;
    background: #0A1322;
}}

QCheckBox::indicator:checked {{
    background: __CYAN__;
    border-color: __CYAN__;
}}

/* =========================================================================
   TABS
   ========================================================================= */
QTabWidget::pane {{
    border: 1px solid #1E2438;
    border-radius: 10px;
    background: __PANEL__;
    top: -1px;
}}

QTabBar::tab {{
    background: transparent;
    color: __MUTED__;
    padding: 8px 16px;
    margin-right: 4px;
    border: 1px solid transparent;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-size: 11px;
    font-weight: 700;
}}

QTabBar::tab:hover {{
    color: __TEXT__;
    background: __PANEL_3__;
}}

QTabBar::tab:selected {{
    background: __PANEL__;
    color: __CYAN__;
    border: 1px solid __CYAN__;
    border-bottom: 2px solid __CYAN__;
}}

/* =========================================================================
   SCROLLBAR
   ========================================================================= */
QScrollBar:vertical {{
    background: transparent;
    width: 9px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: #2A4D7E;
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: #4A7CB8;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: #2A4D7E;
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background: #4A7CB8;
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}

/* =========================================================================
   MENÚ
   ========================================================================= */
QMenu {{
    background: __PANEL_2__;
    border: 1px solid #2A4D7E;
    border-radius: 10px;
    padding: 6px;
}}

QMenu::item {{
    padding: 8px 14px;
    border-radius: 7px;
    color: #D3E0F2;
    font-size: 11px;
}}

QMenu::item:selected {{
    background: #1B2C49;
    color: #FFFFFF;
}}

QMenu::separator {{
    height: 1px;
    background: #22314A;
    margin: 5px 8px;
}}

* {{
    outline: 0;
}}
"""


def _build_qss() -> str:
    """Construye el QSS final reemplazando placeholders por colores reales."""
    qss = _QSS_TEMPLATE
    replacements = {
        "__BG__": BG,
        "__PANEL__": PANEL,
        "__PANEL_2__": PANEL_2,
        "__PANEL_3__": PANEL_3,
        "__CYAN__": CYAN,
        "__MAGENTA__": MAGENTA,
        "__PURPLE__": PURPLE,
        "__AMBER__": AMBER,
        "__GREEN__": GREEN,
        "__TEXT__": TEXT,
        "__MUTED__": MUTED,
        "__DARK__": DARK,
    }
    for key, value in replacements.items():
        qss = qss.replace(key, value)
    return qss


QSS = _build_qss()

# Paleta exportada para uso en código Python
PALETTE = {
    "bg": BG,
    "panel": PANEL,
    "panel2": PANEL_2,
    "panel3": PANEL_3,
    "cyan": CYAN,
    "magenta": MAGENTA,
    "purple": PURPLE,
    "amber": AMBER,
    "green": GREEN,
    "text": TEXT,
    "muted": MUTED,
    "dark": DARK,
    "ok": STATUS_OK,
    "warn": STATUS_WARN,
    "error": STATUS_ERROR,
    "idle": STATUS_IDLE,
}

__all__ = ["QSS", "PALETTE", "BG", "PANEL", "PANEL_2", "PANEL_3",
           "CYAN", "MAGENTA", "PURPLE", "AMBER", "GREEN",
           "TEXT", "MUTED", "DARK",
           "STATUS_OK", "STATUS_WARN", "STATUS_ERROR", "STATUS_IDLE"]
