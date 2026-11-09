#!/usr/bin/env python3
"""Script para compilar archivos de traducción (.po a .mo).

Uso:
    python scripts/compile_translations.py

Requisitos:
    - No se necesitan herramientas externas
    - Usa el módulo estándar gettext (incluido en Python)
"""
from __future__ import annotations

import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Directorios
PROJECT_ROOT = Path(__file__).parent.parent
LOCALES_DIR = PROJECT_ROOT / "voxforge" / "i18n" / "locales"


def compile_po_to_mo(po_path: Path) -> Path | None:
    """Compila un archivo .po a .mo.
    
    Args:
        po_path: Ruta al archivo .po.
    
    Returns:
        Ruta al archivo .mo generado o None si falla.
    """
    import polib
    
    try:
        # Cargar el archivo .po
        po = polib.pofile(po_path)
        
        # Path de salida (.mo en el mismo directorio)
        mo_path = po_path.with_suffix('.mo')
        
        # Compilar y guardar
        po.save_as_mofile(mo_path)
        
        logger.info(f"Compilado: {po_path} -> {mo_path}")
        return mo_path
    except Exception as e:
        logger.error(f"Error al compilar {po_path}: {e}")
        return None


def compile_all_translations() -> int:
    """Compila todas las traducciones en el directorio de locales.
    
    Returns:
        Número de archivos compilados correctamente.
    """
    if not LOCALES_DIR.exists():
        logger.error(f"Directorio de locales no encontrado: {LOCALES_DIR}")
        return 0
    
    compiled_count = 0
    
    # Buscar todos los archivos .po
    for po_path in LOCALES_DIR.rglob("*.po"):
        result = compile_po_to_mo(po_path)
        if result:
            compiled_count += 1
    
    logger.info(f"Total compilados: {compiled_count}")
    return compiled_count


def main() -> int:
    """Función principal."""
    try:
        # Verificar que polib esté disponible
        import polib
    except ImportError:
        logger.error("polib no está instalado. Instálalo con: pip install polib")
        return 1
    
    logger.info("Compilando traducciones...")
    count = compile_all_translations()
    
    if count == 0:
        logger.warning("No se encontraron archivos .po para compilar")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
