"""Soporte de internacionalización (i18n) para VoxForge Local.

Este módulo proporciona:
- Traducciones para CLI (usando gettext)
- Traducciones para GUI (usando Qt Translation)
- Soporte para múltiples idiomas
- Carga automática de traducciones basadas en el idioma configurado

Estructura de archivos de traducción:
    voxforge/i18n/locales/
        es/
            LC_MESSAGES/
                voxforge_cli.mo
                voxforge_cli.po
                voxforge_gui.mo  
                voxforge_gui.po
        en/
            LC_MESSAGES/
                ...
        fr/
            LC_MESSAGES/
                ...

Uso para CLI:
    from voxforge.i18n import get_cli_translator
    
    # Inicializar traducciones
    translator = get_cli_translator('es')
    
    # Usar en código
    _ = translator.gettext
    print(_("Hola mundo"))

Uso para GUI (Qt):
    from voxforge.i18n import load_qt_translation
    
    # Cargar traducción
    translator = load_qt_translation('es')
    app.installTranslator(translator)
"""
from __future__ import annotations

import gettext
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QTranslator

logger = logging.getLogger(__name__)


# =============================================================================
# Constantes
# =============================================================================

LOCALES_DIR = Path(__file__).parent / "locales"
CLI_DOMAIN = "voxforge_cli"
GUI_DOMAIN = "voxforge_gui"

# Idiomas soportados
SUPPORTED_LANGUAGES = [
    "es",  # Español
    "en",  # Inglés
    "fr",  # Francés
    "de",  # Alemán
    "it",  # Italiano
    "pt",  # Portugués
    "ru",  # Ruso
    "zh",  # Chino
    "ja",  # Japonés
    "ar",  # Árabe
]


# =============================================================================
# Traducciones para CLI (gettext)
# =============================================================================

class CLITranslator:
    """Traductor para la interfaz de línea de comandos."""
    
    def __init__(self, language: str = "es"):
        """Inicializa el traductor para CLI.
        
        Args:
            language: Código de idioma (ej: 'es', 'en').
        """
        self.language = language
        self._translator = None
        self._load()
    
    def _load(self) -> None:
        """Carga el catálogo de traducciones."""
        try:
            # Buscar en el directorio de locales
            locale_dir = LOCALES_DIR / self.language / "LC_MESSAGES"
            
            if locale_dir.exists():
                self._translator = gettext.translation(
                    CLI_DOMAIN,
                    localedir=str(LOCALES_DIR),
                    languages=[self.language],
                    fallback=True,
                )
            else:
                # Fallback a inglés o español
                logger.warning(f"No se encontraron traducciones para '{self.language}', usando fallback")
                self._translator = gettext.translation(
                    CLI_DOMAIN,
                    localedir=str(LOCALES_DIR),
                    languages=["en", "es"],
                    fallback=True,
                )
        except Exception as e:
            logger.error(f"Error al cargar traducciones: {e}")
            # Crear traductor vacío
            self._translator = gettext.NullTranslations()
    
    def gettext(self, text: str) -> str:
        """Traduce un texto."""
        if self._translator:
            return self._translator.gettext(text)
        return text
    
    def _(self, text: str) -> str:
        """Atajo para gettext."""
        return self.gettext(text)
    
    def ngettext(self, singular: str, plural: str, n: int) -> str:
        """Traduce texto con pluralización."""
        if self._translator:
            return self._translator.ngettext(singular, plural, n)
        return singular if n == 1 else plural


def get_cli_translator(language: str = "es") -> CLITranslator:
    """Obtiene un traductor para CLI.
    
    Args:
        language: Código de idioma.
    
    Returns:
        Traductor de CLI.
    """
    return CLITranslator(language)


# =============================================================================
# Traducciones para GUI (Qt)
# =============================================================================

def load_qt_translation(language: str = "es") -> "QTranslator | None":
    """Carga un traductor de Qt para la interfaz gráfica.
    
    Args:
        language: Código de idioma.
    
    Returns:
        QTranslator cargado o None si falla.
    """
    try:
        from PySide6.QtCore import QTranslator
    except ImportError:
        logger.error("PySide6 no está disponible")
        return None
    
    translator = QTranslator()
    
    # Intentar cargar la traducción
    # Qt busca en: /path/to/app/translations/app_es.qm
    # También busca en QLibraryInfo::path(QLibraryInfo::TranslationsPath)
    
    locales_to_try = [language, "en", "es"]
    
    for loc in locales_to_try:
        # Buscar en el directorio de locales
        qm_path = LOCALES_DIR / loc / f"{GUI_DOMAIN}.qm"
        if qm_path.exists():
            if translator.load(str(qm_path)):
                logger.info(f"Traducción Qt cargada: {qm_path}")
                return translator
        
        # Buscar con el nombre de dominio
        qm_path = LOCALES_DIR / loc / f"voxforge_gui_{loc}.qm"
        if qm_path.exists():
            if translator.load(str(qm_path)):
                logger.info(f"Traducción Qt cargada: {qm_path}")
                return translator
    
    logger.warning(f"No se encontró traducción Qt para '{language}'")
    return translator


def install_qt_translator(app, language: str = "es") -> bool:
    """Instala el traductor de Qt en la aplicación.
    
    Args:
        app: La aplicación Qt (QApplication).
        language: Código de idioma.
    
    Returns:
        True si se instaló correctamente, False si falló.
    """
    translator = load_qt_translation(language)
    if translator:
        app.installTranslator(translator)
        return True
    return False


# =============================================================================
# Funciones de utilidad
# =============================================================================

def get_supported_languages() -> list[str]:
    """Devuelve la lista de idiomas soportados."""
    return SUPPORTED_LANGUAGES.copy()


def get_language_name(language_code: str) -> str:
    """Devuelve el nombre legible de un idioma."""
    language_names = {
        "es": "Español",
        "en": "English",
        "fr": "Français",
        "de": "Deutsch",
        "it": "Italiano",
        "pt": "Português",
        "ru": "Русский",
        "zh": "中文",
        "ja": "日本語",
        "ar": "العربية",
    }
    return language_names.get(language_code, language_code)


# =============================================================================
# Crear estructura de directorios
# =============================================================================

def create_locales_structure() -> None:
    """Crea la estructura de directorios para las traducciones."""
    for lang in SUPPORTED_LANGUAGES:
        locale_dir = LOCALES_DIR / lang / "LC_MESSAGES"
        locale_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Creado directorio: {locale_dir}")
