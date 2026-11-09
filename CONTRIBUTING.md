# Contribuyendo a VoxForge Local

¡Gracias por tu interés en contribuir a VoxForge Local! 

Este documento describe cómo puedes contribuir al proyecto de manera efectiva.

## 📋 Guía de Contribución

### 1. Reportar Problemas

Antes de reportar un problema:
- Verifica que el problema no haya sido reportado anteriormente
- Proporciona una descripción clara y concisa del problema
- Incluye los pasos para reproducirlo
- Indica la versión de Python y del sistema operativo
- Incluye el mensaje de error completo si existe

### 2. Solicitar Funcionalidades

- Abre un Issue con la etiqueta `feature-request`
- Describe la funcionalidad deseada y su caso de uso
- Explica por qué esta funcionalidad es útil

### 3. Enviar Pull Requests

1. Haz un fork del repositorio
2. Crea una rama para tu funcionalidad o corrección (`git checkout -b feature/mi-funcionalidad`)
3. Realiza tus cambios
4. Ejecuta las pruebas: `python -m pytest tests/`
5. Verifica que el código siga las guías de estilo
6. Envía un Pull Request

## 🎯 Guías de Estilo de Código

### Convenciones de Nombrado

**Seguir PEP 8 estrictamente:**

| Tipo | Convención | Ejemplo |
|------|------------|---------|
| **Módulos** | snake_case | `cache_manager.py` |
| **Clases** | PascalCase | `CacheManager` |
| **Funciones** | snake_case | `cleanup_cache()` |
| **Variables** | snake_case | `cache_dir` |
| **Constantes** | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| **Métodos privados** | _snake_case | `_load_config()` |
| **Métodos protegidos** | _snake_case | `_validate_input()` |

### Estructura de Archivos

```python
"""Descripción del módulo."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)

# Constantes
MAX_RETRIES = 3

# Clases
class MyClass:
    """Descripción de la clase."""
    
    def __init__(self, param: str) -> None:
        """Inicializa la clase.
        
        Args:
            param: Descripción del parámetro.
        """
        self.param = param
    
    def my_method(self, arg: int) -> str:
        """Descripción del método.
        
        Args:
            arg: Descripción del argumento.
        
        Returns:
            Descripción del valor de retorno.
        """
        return str(arg)

# Funciones
def my_function(param: str) -> int:
    """Descripción de la función.
    
    Args:
        param: Descripción del parámetro.
    
    Returns:
        Descripción del valor de retorno.
    """
    return len(param)

# Código principal
if __name__ == "__main__":
    main()
```

### Type Hints

**Siempre usar type hints en funciones públicas:**

```python
# ✅ Bien
def process_text(text: str, max_length: int = 100) -> str:
    return text[:max_length]

# ❌ Mal (falta type hint)
def process_text(text, max_length=100):
    return text[:max_length]
```

**Usar `TYPE_CHECKING` para importaciones condicionales:**

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .other_module import SomeClass
```

### Docstrings

**Usar estilo Google para docstrings:**

```python
def my_function(param1: str, param2: int = 10) -> list[str]:
    """Descripción breve de la función.
    
    Descripción más detallada si es necesario.
    
    Args:
        param1: Descripción del primer parámetro.
        param2: Descripción del segundo parámetro. Default 10.
    
    Returns:
        Descripción del valor de retorno.
    
    Raises:
        ValueError: Si param1 está vacío.
        RuntimeError: Si ocurre un error durante el procesamiento.
    
    Example:
        >>> my_function("hello", 5)
        ['hello']
    """
```

### Logging

**Usar logging en lugar de print():**

```python
import logging

logger = logging.getLogger(__name__)

# ✅ Bien
logger.debug("Mensaje de debug")
logger.info("Mensaje informativo")
logger.warning("Advertencia")
logger.error("Error")
logger.exception("Error con traceback")

# ❌ Mal (en código de producción)
print("Mensaje")
```

### Manejo de Errores

**Usar excepciones específicas:**

```python
# ✅ Bien
class CacheError(Exception):
    """Error relacionado con la caché."""
    pass

raise CacheError("No se pudo limpiar la caché")

# ❌ Mal (demasiado genérico)
raise Exception("Error")
```

**Usar subprocess.run con check=True:**

```python
import subprocess

# ✅ Bien
try:
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_file, output_file],
        capture_output=True,
        text=True,
        check=True,  # Esto es importante!
    )
except subprocess.CalledProcessError as e:
    logger.error(f"ffmpeg falló: {e.stderr}")
    raise

# ❌ Mal (no verifica el código de retorno)
result = subprocess.run(["ffmpeg", ...])
if result.returncode != 0:
    # Esto puede ser olvidado
    pass
```

### Comentarios

**Los comentarios deben explicar POR QUÉ, no QUÉ:**

```python
# ✅ Bien - explica por qué
# Usamos 220 caracteres como máximo porque XTTS en español
# admite ~239 caracteres por fragmento
max_chunk_chars = 220

# ❌ Mal - explica qué (evidente)
# Máximo número de caracteres por fragmento
max_chunk_chars = 220
```

## 🔧 Configuración del Entorno de Desarrollo

### Requisitos Previos

- Python 3.10+
- pip
- virtualenv (recomendado)

### Crear Entorno Virtual

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .\.venv\Scripts\activate  # Windows
```

### Instalar Dependencias

```bash
pip install -e .
# o
pip install -r requirements.txt
```

### Instalar Herramientas de Desarrollo

```bash
pip install pytest pytest-cov mypy ruff black
```

## 🧪 Ejecutar Pruebas

### Todas las pruebas

```bash
python -m pytest tests/
```

### Pruebas específicas

```bash
python -m pytest tests/test_core.py
python -m pytest tests/test_audio_quality.py
```

### Con cobertura

```bash
python -m pytest tests/ --cov=voxforge --cov-report=html
```

## 📊 Verificación de Calidad de Código

### Linting con ruff

```bash
ruff check voxforge/ gui.py
```

### Formateo con black

```bash
black voxforge/ gui.py
```

### Type checking con mypy

```bash
mypy voxforge/ gui.py
```

## 📝 Convenciones de Commit

Usamos commits atómicos con mensajes descriptivos:

```bash
# ✅ Bien
git commit -m "Fix cache cleanup by age to handle empty directories"
git commit -m "Add Pydantic settings for improved validation"

# ❌ Mal
git commit -m "fix"
git commit -m "wip"
```

Formato recomendado:
- **feat:** Nueva funcionalidad
- **fix:** Corrección de bug
- **refactor:** Refactorización de código
- **docs:** Cambios en documentación
- **style:** Cambios de estilo (formato, etc.)
- **test:** Añadir/actualizar pruebas
- **chore:** Tareas de mantenimiento

Ejemplo:
```bash
git commit -m "feat: add cache cleanup by size with LRU policy"
git commit -m "fix: handle empty cache directory gracefully"
git commit -m "refactor: move cache logic to separate module"
```

## 🤝 Código de Conducta

Al contribuir a este proyecto, aceptas:
- Ser respetuoso con otros contribuidores
- Seguir las guías de estilo del proyecto
- Proporcionar código de calidad
- Documentar adecuadamente tus cambios
- Ayudar a mantener un ambiente de comunidad positiva

## 📄 Licencia

Al contribuir código a este proyecto, aceptas que tu contribución será licenciada bajo los términos de la licencia MIT del proyecto.

---

¡Gracias por tu contribución a VoxForge Local! 🎉
