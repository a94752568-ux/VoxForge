"""NOVA Premium Theme for VoxForge Local.

A cyberpunk-inspired professional theme with electric blue accents,
dark backgrounds, and futuristic holographic elements.

Inspired by the NOVA Cognitive Operations System design.

Usage:
    from voxforge.themes.nova_premium import NOVA_THEME
    app.setStyleSheet(NOVA_THEME)
"""

from __future__ import annotations

# =============================================================================
# NOVA Color Palette - Professional Cyberpunk Theme
# =============================================================================

# Primary Colors
NOVA_BG_PRIMARY = "#0a0a0f"        # Deep space black
NOVA_BG_SECONDARY = "#12121a"      # Dark background
NOVA_BG_TERTIARY = "#1a1a25"       # Card/panel background
NOVA_BG_QUATERNARY = "#202030"     # Elevated surfaces

# Accent Colors (Electric Blue/Cyan)
NOVA_ACCENT_PRIMARY = "#00ffff"     # Bright electric cyan
NOVA_ACCENT_SECONDARY = "#00b4ff"    # Secondary blue
NOVA_ACCENT_TERTIARY = "#0066cc"    # Deeper blue
NOVA_ACCENT_QUATERNARY = "#003366"  # Dark accent

# Text Colors
NOVA_TEXT_PRIMARY = "#e0e0ff"       # Primary text (soft white)
NOVA_TEXT_SECONDARY = "#a0a0d0"     # Secondary text
NOVA_TEXT_TERTIARY = "#606090"      # Muted text
NOVA_TEXT_ACCENT = "#00ffff"        # Accent text

# Border Colors
NOVA_BORDER_PRIMARY = "#2a2a40"     # Primary border
NOVA_BORDER_ACCENT = "#0066cc"      # Accent border
NOVA_BORDER_GLOW = "#00ffff"        # Glowing border effect

# Status Colors
NOVA_SUCCESS = "#00ff88"           # Success green
NOVA_WARNING = "#ffaa00"           # Warning amber
NOVA_ERROR = "#ff3366"             # Error red
NOVA_INFO = "#00aaff"              # Info blue

# Gradient Definitions
NOVA_GRADIENT_ACCENT = f"""
    qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {NOVA_ACCENT_PRIMARY},
        stop:0.5 {NOVA_ACCENT_SECONDARY},
        stop:1 {NOVA_ACCENT_TERTIARY})
"""

NOVA_GRADIENT_BG = f"""
    qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {NOVA_BG_SECONDARY},
        stop:1 {NOVA_BG_PRIMARY})
"""

NOVA_GRADIENT_BUTTON = f"""
    qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {NOVA_ACCENT_SECONDARY},
        stop:1 {NOVA_ACCENT_TERTIARY})
"""


# =============================================================================
# NOVA Premium Theme - Main QSS Stylesheet
# =============================================================================

NOVA_THEME = f"""
/* =============================================================================
   NOVA PREMIUM THEME - VoxForge Local
   Cyberpunk Professional Theme
   ============================================================================= */

/* Base Application */
QApplication {{
    background-color: {NOVA_BG_PRIMARY};
    color: {NOVA_TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Noto Sans', 'Ubuntu', 'Cantarell', sans-serif;
    font-size: 13px;
}}

/* =============================================================================
   MAIN WINDOW
   ============================================================================= */

MainWindow {{
    background-color: {NOVA_BG_SECONDARY};
    background: {NOVA_GRADIENT_BG};
    border: 1px solid {NOVA_BORDER_PRIMARY};
    border-radius: 12px;
    padding: 0px;
    color: {NOVA_TEXT_PRIMARY};
}}

MainWindow QWidget {{
    background-color: {NOVA_BG_SECONDARY};
    color: {NOVA_TEXT_PRIMARY};
}}

/* =============================================================================
   HEADER AND TITLE BARS
   ============================================================================= */

QHeaderView {{
    background-color: {NOVA_BG_TERTIARY};
    color: {NOVA_TEXT_ACCENT};
    border: none;
    border-bottom: 2px solid {NOVA_BORDER_ACCENT};
    padding: 8px;
    font-weight: 600;
}}

QHeaderView::section {{
    background-color: {NOVA_BG_TERTIARY};
    color: {NOVA_TEXT_ACCENT};
    padding: 6px 12px;
    border: none;
    border-bottom: 1px solid {NOVA_BORDER_PRIMARY};
    text-align: left;
}}

QHeaderView::section:checked {{
    background-color: {NOVA_ACCENT_TERTIARY};
}}

/* Title Bar */
QLabel[title="true"] {{
    color: {NOVA_ACCENT_PRIMARY};
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 2px;
    text-shadow: 0 0 10px {NOVA_ACCENT_PRIMARY};
    margin: 8px 16px;
}}

/* =============================================================================
   BUTTONS
   ============================================================================= */

/* Primary Buttons (Accent) */
QPushButton[primary="true"],
QPushButton#btn_primary {{
    background: {NOVA_GRADIENT_BUTTON};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_ACCENT};
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: 600;
    min-height: 40px;
}}

QPushButton[primary="true"]:hover,
QPushButton#btn_primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {NOVA_ACCENT_PRIMARY},
        stop:1 {NOVA_ACCENT_SECONDARY});
    border: 2px solid {NOVA_ACCENT_PRIMARY};
}}

QPushButton[primary="true"]:pressed,
QPushButton#btn_primary:pressed {{
    background: {NOVA_ACCENT_TERTIARY};
    border: 2px solid {NOVA_ACCENT_PRIMARY};
}}

/* Standard Buttons */
QPushButton {{
    background-color: {NOVA_BG_QUATERNARY};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 13px;
    min-height: 36px;
}}

QPushButton:hover {{
    background-color: {NOVA_BG_TERTIARY};
    border: 2px solid {NOVA_BORDER_ACCENT};
    color: {NOVA_TEXT_ACCENT};
}}

QPushButton:pressed {{
    background-color: {NOVA_ACCENT_TERTIARY};
    color: {NOVA_TEXT_PRIMARY};
}}

QPushButton:disabled {{
    background-color: {NOVA_BG_PRIMARY};
    color: {NOVA_TEXT_TERTIARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
}}

/* Accent Buttons */
QPushButton[accent="true"],
QPushButton#btn_accent {{
    background-color: transparent;
    color: {NOVA_ACCENT_PRIMARY};
    border: 2px solid {NOVA_ACCENT_PRIMARY};
    border-radius: 8px;
    padding: 8px 20px;
    min-height: 36px;
}}

QPushButton[accent="true"]:hover {{
    background: {NOVA_GRADIENT_ACCENT};
    color: {NOVA_TEXT_PRIMARY};
}}

/* Danger Buttons */
QPushButton[danger="true"],
QPushButton#btn_danger {{
    background-color: {NOVA_ERROR};
    color: white;
    border: 2px solid {NOVA_ERROR};
    border-radius: 8px;
    padding: 8px 20px;
    min-height: 36px;
}}

QPushButton[danger="true"]:hover {{
    background-color: #ff5588;
    border: 2px solid #ff77aa;
}}

/* Tool Buttons */
QToolButton {{
    background-color: {NOVA_BG_QUATERNARY};
    color: {NOVA_TEXT_SECONDARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 6px;
    padding: 6px;
}}

QToolButton:hover {{
    background-color: {NOVA_BG_TERTIARY};
    color: {NOVA_TEXT_ACCENT};
    border: 2px solid {NOVA_BORDER_ACCENT};
}}

QToolButton:pressed {{
    background-color: {NOVA_ACCENT_TERTIARY};
    color: white;
}}

/* =============================================================================
   INPUT FIELDS AND TEXT EDITORS
   ============================================================================= */

QLineEdit {{
    background-color: {NOVA_BG_QUATERNARY};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: {NOVA_ACCENT_PRIMARY};
    selection-color: {NOVA_BG_PRIMARY};
}}

QLineEdit:focus {{
    border: 2px solid {NOVA_BORDER_ACCENT};
    background-color: {NOVA_BG_TERTIARY};
}}

QLineEdit:read-only {{
    background-color: {NOVA_BG_PRIMARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    color: {NOVA_TEXT_TERTIARY};
}}

QTextEdit {{
    background-color: {NOVA_BG_QUATERNARY};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 8px;
    padding: 12px;
    font-size: 13px;
    selection-background-color: {NOVA_ACCENT_PRIMARY};
    selection-color: {NOVA_BG_PRIMARY};
}}

QTextEdit:focus {{
    border: 2px solid {NOVA_BORDER_ACCENT};
    background-color: {NOVA_BG_TERTIARY};
}}

QPlainTextEdit {{
    background-color: {NOVA_BG_QUATERNARY};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 8px;
    padding: 12px;
    font-size: 13px;
}}

QPlainTextEdit:focus {{
    border: 2px solid {NOVA_BORDER_ACCENT};
    background-color: {NOVA_BG_TERTIARY};
}}

/* =============================================================================
   COMBO BOXES AND SPIN BOXES
   ============================================================================= */

QComboBox {{
    background-color: {NOVA_BG_QUATERNARY};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 36px;
    selection-background-color: {NOVA_ACCENT_PRIMARY};
    selection-color: {NOVA_BG_PRIMARY};
}}

QComboBox:focus {{
    border: 2px solid {NOVA_BORDER_ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    background-color: transparent;
}}

QComboBox::down-arrow {{
    image: none;
    border: none;
}}

QComboBox QListView {{
    background-color: {NOVA_BG_TERTIARY};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_ACCENT};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {NOVA_ACCENT_TERTIARY};
    selection-color: white;
}}

QSpinBox,
QDoubleSpinBox {{
    background-color: {NOVA_BG_QUATERNARY};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 36px;
}}

QSpinBox:focus,
QDoubleSpinBox:focus {{
    border: 2px solid {NOVA_BORDER_ACCENT};
    background-color: {NOVA_BG_TERTIARY};
}}

QSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button {{
    background-color: {NOVA_BG_PRIMARY};
    color: {NOVA_TEXT_SECONDARY};
    border: 1px solid {NOVA_BORDER_PRIMARY};
    width: 24px;
}}

QSpinBox::up-button:hover,
QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover {{
    background-color: {NOVA_ACCENT_TERTIARY};
    color: white;
}}

/* =============================================================================
   CHECKBOXES AND RADIO BUTTONS
   ============================================================================= */

QCheckBox {{
    spacing: 8px;
    color: {NOVA_TEXT_PRIMARY};
}}

QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 4px;
    background-color: {NOVA_BG_QUATERNARY};
}}

QCheckBox::indicator:checked {{
    background: {NOVA_GRADIENT_ACCENT};
    border: 2px solid {NOVA_BORDER_ACCENT};
    image: url(:/icons/check);
}}

QCheckBox::indicator:hover {{
    border: 2px solid {NOVA_BORDER_ACCENT};
}}

QRadioButton {{
    spacing: 8px;
    color: {NOVA_TEXT_PRIMARY};
}}

QRadioButton::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 10px;
    background-color: {NOVA_BG_QUATERNARY};
}}

QRadioButton::indicator:checked {{
    background: {NOVA_GRADIENT_ACCENT};
    border: 2px solid {NOVA_BORDER_ACCENT};
}}

/* =============================================================================
   SLIDERS
   ============================================================================= */

QSlider::groove:horizontal {{
    background-color: {NOVA_BG_QUATERNARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 4px;
    height: 8px;
}}

QSlider::handle:horizontal {{
    background: {NOVA_GRADIENT_ACCENT};
    border: 2px solid {NOVA_BORDER_ACCENT};
    border-radius: 6px;
    width: 18px;
    height: 18px;
    margin: -5px 0;
}}

QSlider::groove:vertical {{
    background-color: {NOVA_BG_QUATERNARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 4px;
    width: 8px;
}}

QSlider::handle:vertical {{
    background: {NOVA_GRADIENT_ACCENT};
    border: 2px solid {NOVA_BORDER_ACCENT};
    border-radius: 6px;
    width: 18px;
    height: 18px;
    margin: 0 -5px;
}}

/* =============================================================================
   PROGRESS BARS
   ============================================================================= */

QProgressBar {{
    background-color: {NOVA_BG_QUATERNARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 6px;
    text-align: center;
    color: {NOVA_TEXT_PRIMARY};
    font-weight: 600;
}}

QProgressBar::chunk {{
    background: {NOVA_GRADIENT_ACCENT};
    border-radius: 4px;
    margin: 1px;
}}

/* =============================================================================
   Tabs
   ============================================================================= */

QTabWidget::pane {{
    background-color: {NOVA_BG_SECONDARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 8px;
    padding: 0px;
}}

QTabBar::tab {{
    background-color: {NOVA_BG_TERTIARY};
    color: {NOVA_TEXT_SECONDARY};
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    margin: 2px 2px 0 0;
}}

QTabBar::tab:selected {{
    background: {NOVA_GRADIENT_ACCENT};
    color: {NOVA_TEXT_PRIMARY};
    font-weight: 600;
}}

QTabBar::tab:hover {{
    background-color: {NOVA_BG_QUATERNARY};
    color: {NOVA_TEXT_ACCENT};
}}

/* =============================================================================
   TABLES AND TREE VIEWS
   ============================================================================= */

QTableView {{
    background-color: {NOVA_BG_TERTIARY};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 8px;
    gridline-color: {NOVA_BORDER_PRIMARY};
    selection-background-color: {NOVA_ACCENT_TERTIARY};
    selection-color: white;
    alternate-background-color: {NOVA_BG_QUATERNARY};
}}

QTableView::item:selected {{
    background-color: {NOVA_ACCENT_TERTIARY};
    color: white;
}}

QTableView::item:hover {{
    background-color: {NOVA_BG_QUATERNARY};
}}

QTreeView {{
    background-color: {NOVA_BG_TERTIARY};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 8px;
    selection-background-color: {NOVA_ACCENT_TERTIARY};
    selection-color: white;
}}

/* =============================================================================
   GROUP BOXES AND FRAMES
   ============================================================================= */

QGroupBox {{
    background-color: {NOVA_BG_SECONDARY};
    color: {NOVA_TEXT_ACCENT};
    border: 2px solid {NOVA_BORDER_ACCENT};
    border-radius: 8px;
    padding: 12px;
    margin-top: 8px;
    font-weight: 600;
    font-size: 14px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {NOVA_ACCENT_PRIMARY};
}}

QFrame {{
    background-color: {NOVA_BG_TERTIARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 8px;
}}

QFrame[bordered="false"] {{
    border: none;
    background-color: transparent;
}}

/* =============================================================================
   SCROLLBARS
   ============================================================================= */

QScrollBar:vertical {{
    background-color: {NOVA_BG_PRIMARY};
    border: none;
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {NOVA_ACCENT_TERTIARY};
    border-radius: 6px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {NOVA_ACCENT_SECONDARY};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    background-color: transparent;
    border: none;
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {NOVA_BG_PRIMARY};
    border: none;
    height: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal {{
    background-color: {NOVA_ACCENT_TERTIARY};
    border-radius: 6px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {NOVA_ACCENT_SECONDARY};
}}

/* =============================================================================
   TOOLTIPS
   ============================================================================= */

QToolTip {{
    background-color: {NOVA_BG_TERTIARY};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_ACCENT};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
}}

/* =============================================================================
   MENU BAR AND MENUS
   ============================================================================= */

QMenuBar {{
    background-color: {NOVA_BG_PRIMARY};
    color: {NOVA_TEXT_PRIMARY};
    border: none;
    padding: 4px;
}}

QMenuBar::item {{
    background-color: transparent;
    color: {NOVA_TEXT_SECONDARY};
    padding: 8px 16px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {NOVA_ACCENT_TERTIARY};
    color: white;
}}

QMenu {{
    background-color: {NOVA_BG_TERTIARY};
    color: {NOVA_TEXT_PRIMARY};
    border: 2px solid {NOVA_BORDER_ACCENT};
    border-radius: 8px;
    padding: 4px;
    margin: 2px;
}}

QMenu::item {{
    background-color: transparent;
    color: {NOVA_TEXT_PRIMARY};
    padding: 8px 16px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {NOVA_ACCENT_TERTIARY};
    color: white;
}}

QMenu::separator {{
    background-color: {NOVA_BORDER_PRIMARY};
    height: 1px;
    margin: 4px 0;
}}

/* =============================================================================
   STATUS BAR
   ============================================================================= */

QStatusBar {{
    background-color: {NOVA_BG_PRIMARY};
    color: {NOVA_TEXT_SECONDARY};
    border-top: 2px solid {NOVA_BORDER_PRIMARY};
    padding: 8px 12px;
    font-size: 12px;
}}

QStatusBar QLabel {{
    color: {NOVA_TEXT_SECONDARY};
    padding: 2px 8px;
}}

/* =============================================================================
   LABELS
   ============================================================================= */

QLabel {{
    color: {NOVA_TEXT_PRIMARY};
    background-color: transparent;
}}

QLabel[secondary="true"] {{
    color: {NOVA_TEXT_SECONDARY};
}}

QLabel[accent="true"] {{
    color: {NOVA_ACCENT_PRIMARY};
    font-weight: 600;
}}

QLabel[success="true"] {{
    color: {NOVA_SUCCESS};
    font-weight: 600;
}}

QLabel[warning="true"] {{
    color: {NOVA_WARNING};
    font-weight: 600;
}}

QLabel[error="true"] {{
    color: {NOVA_ERROR};
    font-weight: 600;
}}

/* =============================================================================
   HOVER AND GLOW EFFECTS
   ============================================================================= */

QWidget:hover {{
    /* Subtle hover effect */
}}

QPushButton[glow="true"] {{
    background: {NOVA_GRADIENT_BUTTON};
    border: 2px solid {NOVA_BORDER_ACCENT};
    border-radius: 12px;
}}

/* =============================================================================
   NOVA-SPECIFIC WIDGETS
   ============================================================================= */

/* Voice Profile Cards */
QFrame#voice_card {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {NOVA_BG_TERTIARY},
        stop:1 {NOVA_BG_QUATERNARY});
    border: 2px solid {NOVA_BORDER_ACCENT};
    border-radius: 12px;
    padding: 16px;
    margin: 8px;
}}

/* Project Cards */
QFrame#project_card {{
    background-color: {NOVA_BG_TERTIARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 12px;
    padding: 16px;
    margin: 8px;
}}

QFrame#project_card:hover {{
    border: 2px solid {NOVA_BORDER_ACCENT};
}}

/* Waveform Display */
QFrame#waveform {{
    background-color: {NOVA_BG_PRIMARY};
    border: 2px solid {NOVA_BORDER_ACCENT};
    border-radius: 8px;
}}

/* Audio Player Controls */
QFrame#player_controls {{
    background-color: {NOVA_BG_TERTIARY};
    border: 2px solid {NOVA_BORDER_PRIMARY};
    border-radius: 12px;
    padding: 12px;
}}

/* Progress Indicator */
QProgressBar#progress_indicator {{
    background-color: {NOVA_BG_QUATERNARY};
    border: 2px solid {NOVA_ACCENT_PRIMARY};
    border-radius: 6px;
    text-align: center;
}}

QProgressBar#progress_indicator::chunk {{
    background: {NOVA_GRADIENT_ACCENT};
    border-radius: 4px;
}}

/* =============================================================================
   FINAL TOUCHES
   ============================================================================= */

* {{
    outline: none;
}}

QWidget {{
    background-color: {NOVA_BG_SECONDARY};
    color: {NOVA_TEXT_PRIMARY};
}}
"""


# =============================================================================
# NOVA CLI Theme (for terminal output)
# =============================================================================

class NOVA_CLI_Theme:
    """ANSI color codes for NOVA theme in terminal output."""
    
    # Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # NOVA-specific colors (using CYAN as primary accent)
    PRIMARY = CYAN           # Electric blue/cyan
    SECONDARY = BRIGHT_CYAN  # Brighter accent
    TEXT = WHITE             # Primary text
    TEXT_MUTED = BRIGHT_BLACK
    BG = BLACK               # Background
    
    # Status colors
    SUCCESS = GREEN
    WARNING = YELLOW
    ERROR = RED
    INFO = CYAN
    
    # Formatting
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"
    
    # NOVA styled text
    @staticmethod
    def header(text: str) -> str:
        return f"{NOVA_CLI_Theme.BOLD}{NOVA_CLI_Theme.PRIMARY}{text}{NOVA_CLI_Theme.RESET}"
    
    @staticmethod
    def title(text: str) -> str:
        return f"{NOVA_CLI_Theme.BOLD}{NOVA_CLI_Theme.BRIGHT_CYAN}{text}{NOVA_CLI_Theme.RESET}"
    
    @staticmethod
    def accent(text: str) -> str:
        return f"{NOVA_CLI_Theme.PRIMARY}{text}{NOVA_CLI_Theme.RESET}"
    
    @staticmethod
    def success(text: str) -> str:
        return f"{NOVA_CLI_Theme.SUCCESS}{text}{NOVA_CLI_Theme.RESET}"
    
    @staticmethod
    def warning(text: str) -> str:
        return f"{NOVA_CLI_Theme.WARNING}{text}{NOVA_CLI_Theme.RESET}"
    
    @staticmethod
    def error(text: str) -> str:
        return f"{NOVA_CLI_Theme.ERROR}{text}{NOVA_CLI_Theme.RESET}"
    
    @staticmethod
    def info(text: str) -> str:
        return f"{NOVA_CLI_Theme.INFO}{text}{NOVA_CLI_Theme.RESET}"
    
    @staticmethod
    def muted(text: str) -> str:
        return f"{NOVA_CLI_Theme.TEXT_MUTED}{text}{NOVA_CLI_Theme.RESET}"
    
    @staticmethod
    def bold(text: str) -> str:
        return f"{NOVA_CLI_Theme.BOLD}{text}{NOVA_CLI_Theme.RESET}"
    
    @staticmethod
    def dim(text: str) -> str:
        return f"{NOVA_CLI_Theme.DIM}{text}{NOVA_CLI_Theme.RESET}"


# =============================================================================
# Theme Metadata
# =============================================================================

NOVA_THEME_INFO = {
    "name": "NOVA Premium",
    "version": "1.0.0",
    "description": "Cyberpunk-inspired professional theme for VoxForge Local",
    "author": "NOVA Cognitive Operations System",
    "colors": {
        "primary": NOVA_ACCENT_PRIMARY,
        "secondary": NOVA_ACCENT_SECONDARY,
        "background": NOVA_BG_PRIMARY,
        "text": NOVA_TEXT_PRIMARY,
        "success": NOVA_SUCCESS,
        "warning": NOVA_WARNING,
        "error": NOVA_ERROR,
    },
    "type": "dark",
}


def apply_nova_theme(app) -> None:
    """Apply NOVA theme to a Qt application.
    
    Args:
        app: QApplication instance
    """
    app.setStyleSheet(NOVA_THEME)
    app.setPalette(create_nova_palette())


def create_nova_palette() -> "QPalette":
    """Create a QPalette for NOVA theme.
    
    Returns:
        QPalette instance with NOVA colors
    """
    from PySide6.QtGui import QPalette, QColor
    
    palette = QPalette()
    
    # Base colors
    palette.setColor(QPalette.Window, QColor(NOVA_BG_PRIMARY))
    palette.setColor(QPalette.WindowText, QColor(NOVA_TEXT_PRIMARY))
    palette.setColor(QPalette.Base, QColor(NOVA_BG_QUATERNARY))
    palette.setColor(QPalette.AlternateBase, QColor(NOVA_BG_TERTIARY))
    palette.setColor(QPalette.Text, QColor(NOVA_TEXT_PRIMARY))
    palette.setColor(QPalette.Button, QColor(NOVA_BG_QUATERNARY))
    palette.setColor(QPalette.ButtonText, QColor(NOVA_TEXT_PRIMARY))
    palette.setColor(QPalette.BrightText, QColor(NOVA_ACCENT_PRIMARY))
    palette.setColor(QPalette.Highlight, QColor(NOVA_ACCENT_PRIMARY))
    palette.setColor(QPalette.HighlightedText, QColor(NOVA_BG_PRIMARY))
    
    # Disabled colors
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(NOVA_TEXT_TERTIARY))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(NOVA_TEXT_TERTIARY))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(NOVA_TEXT_TERTIARY))
    
    # Link colors
    palette.setColor(QPalette.Link, QColor(NOVA_ACCENT_PRIMARY))
    palette.setColor(QPalette.LinkVisited, QColor(NOVA_ACCENT_SECONDARY))
    
    # Tool tip colors
    palette.setColor(QPalette.ToolTipBase, QColor(NOVA_BG_TERTIARY))
    palette.setColor(QPalette.ToolTipText, QColor(NOVA_TEXT_PRIMARY))
    
    return palette


# =============================================================================
# Quick Theme Preview
# =============================================================================

if __name__ == "__main__":
    # Test CLI theme
    print(f"\n{NOVA_CLI_Theme.title('NOVA PREMIUM THEME - VoxForge Local')}")
    print(f"{NOVA_CLI_Theme.header('=' * 50)}")
    print(f"\n{NOVA_CLI_Theme.accent('Theme Colors:')}")
    print(f"  Primary:    {NOVA_CLI_Theme.PRIMARY}■{NOVA_CLI_Theme.RESET} {NOVA_ACCENT_PRIMARY}")
    print(f"  Secondary:  {NOVA_CLI_Theme.SECONDARY}■{NOVA_CLI_Theme.RESET} {NOVA_ACCENT_SECONDARY}")
    print(f"  Background:  {NOVA_CLI_Theme.BG}■{NOVA_CLI_Theme.RESET} {NOVA_BG_PRIMARY}")
    print(f"  Text:       {NOVA_CLI_Theme.TEXT}■{NOVA_CLI_Theme.RESET} {NOVA_TEXT_PRIMARY}")
    print(f"\n{NOVA_CLI_Theme.accent('Status Colors:')}")
    print(f"  Success:    {NOVA_CLI_Theme.success('✓ Success')}")
    print(f"  Warning:    {NOVA_CLI_Theme.warning('⚠ Warning')}")
    print(f"  Error:      {NOVA_CLI_Theme.error('✗ Error')}")
    print(f"  Info:       {NOVA_CLI_Theme.info('ℹ Info')}")
    print(f"\n{NOVA_CLI_Theme.muted('Theme applied successfully!')}\n")
