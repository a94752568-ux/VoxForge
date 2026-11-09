# VoxForge Local

> **Estudio de clonación de voz y narración 100% local/offline en Python**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
![Status: Beta](https://img.shields.io/badge/status-Beta-yellow.svg)

---

## ✨ Descripción

**VoxForge Local** es un estudio completo para la creación de audiolibros y narraciones con **clonación de voz 100% local**. No requiere conexión a Internet, no envía datos a la nube, y funciona únicamente con la potencia de tu CPU.

**Características principales:**

- ✅ **Clonación de voz multilingüe** con Coqui XTTS-v2
- ✅ **Síntesis de voz natural** en más de 15 idiomas
- ✅ **Gestión de proyectos** con cap­tulos organizados
- ✅ **Normalización EBU R128** para calidad de estudio profesional
- ✅ **Sistema de caché inteligente** para reanudar narraciones interrumpidas
- ✅ **Interfaz CLI y GUI** con PySide6
- ✅ **100% offline** - Todo el procesamiento se realiza localmente
- ✅ **Solo CPU** - Compatible con sistemas sin GPU

---

## ⚡ Requisitos del Sistema

| Requisito | Mínimo | Recomendado |
|-----------|------------|-------------|
| **Sistema Operativo** | Linux, Windows, macOS | Linux (Ubuntu 22.04+) |
| **Python** | 3.10 | 3.11+ |
| **RAM** | 8 GB | 16 GB |
| **CPU** | 4 núcleos | 8+ núcleos (Intel i5/i7/Ryzen) |
| **Almacenamiento** | 5 GB libres | 20 GB libres (para modelos y caché) |
| **GPU** | No requerida | No requerida (funciona solo con CPU) |

---

## ⌈ Instalación

### Opción 1: Instalación con pipx (Recomendado)

```bash
# Instalar pipx (si no lo tienes)
python -m pip install --user pipx
python -m pipx ensurepath

# Clonar el repositorio
git clone https://github.com/tu-usuario/voxforge.git
cd voxforge

# Instalar en modo editable
pipx install -e .

# O instalar globalmente
pipx install .
```

### Opción 2: Instalación con pip

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/voxforge.git
cd voxforge

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .\.venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -e .

# O instalar dependencias desde requirements.txt
pip install -r requirements.txt
```

### Opción 3: Descarga de modelos

Los modelos de XTTS-v2 se descargan automáticamente la primera vez que los usas:

```bash
voxforge model download
```

---

## ⚀ Uso Rápido

### 1. Crear un perfil de voz

Primero, graba una muestra de tu voz (recomendado: 1-5 minutos de audio claro):

```bash
# Grabación directa (el programa te guiará)
voxforge voice record --name mi_voz

# O usando un archivo WAV existente
voxforge voice add mi_voz /ruta/a/tu/muestra.wav --language es
```

### 2. Crear un proyecto

```bash
voxforge project create mi_libro --voice mi_voz --language es
```

### 3. Añadir un capítulo

```bash
# Desde un archivo de texto
voxforge chapter add mi_libro 1 --file capitulo1.txt

# Desde un PDF (se extraerá el texto automáticamente)
voxforge chapter add mi_libro 2 --file capitulo2.pdf

# Desde DOCX, EPUB, MD
voxforge chapter add mi_libro 3 --file capitulo3.docx
```

### 4. Narrar un capítulo

```bash
# Narrar con la voz clonada
voxforge chapter narrate mi_libro 1 --out Capitulo_01.mp3

# Narrar con normalización EBU R128 (calidad de estudio)
voxforge chapter narrate mi_libro 1 --out Capitulo_01.mp3

# Narrar con efectos de voz (opcional)
voxforge chapter narrate mi_libro 1 --fx warm --out Capitulo_01.mp3
```

### 5. Narrar un proyecto completo

```bash
# Narrar todos los capítulos de un proyecto
voxforge project-narrate mi_libro --out-dir audiobook/

# Con formato WAV (sin compresión)
voxforge project-narrate mi_libro --format wav --out-dir audiobook/

# Con formato FLAC (calidad alta, compresión sin pérdida)
voxforge project-narrate mi_libro --format flac --out-dir audiobook/
```

---

## ❓ Interfaz Gráfica

Para iniciar la interfaz gráfica:

```bash
# Con pipx
voxforge-gui

# Con Python
python -m gui

# O directamente
python gui.py
```

La interfaz gráfica ofrece:
- Gestión visual de proyectos y capítulos
- Grabación de voz integrada
- Reproducción de audio
- Monitoreo del progreso de narración
- Configuración de efectos de voz

---

## ⚙ Configuración

### Archivo de configuración

La configuración se guarda en `~/.voxforge/config.json` (Linux/macOS) o `%APPDATA%\voxforge\config.json` (Windows).

```json
{
    "language": "es",
    "voice_profile": "mi_voz",
    "sample_rate": 24000,
    "apply_ebu_r128": true,
    "cache_dir": "data/cache",
    "export_dir": "data/exports",
    "max_retries": 3,
    "auto_unload": true,
    "auto_unload_minutes": 10
}
```

### Opciones de configuración

| Opción | Tipo | Descripción | Valor por defecto |
|--------|------|------------------|-------------------|
| `language` | string | Idioma por defecto | "es" |
| `voice_profile` | string | Perfil de voz por defecto | "yo_limpia" |
| `sample_rate` | int | Frecuencia de muestreo | 24000 |
| `apply_ebu_r128` | bool | Aplicar normalización EBU R128 | true |
| `cache_dir` | string | Directorio de caché | "data/cache" |
| `export_dir` | string | Directorio de exportación | "data/exports" |
| `max_retries` | int | Máximos reintentos de síntesis | 3 |
| `auto_unload` | bool | Descargar modelo automáticamente | true |
| `auto_unload_minutes` | int | Minutos de inactividad antes de descargar | 10 |

---

## ✯ Idiomas Soportados

| Código | Idioma | Nombre nativo |
|-------|--------|----------------|
| `es` | Español | Español |
| `en` | Inglés | English |
| `fr` | Francés | Français |
| `de` | Alemán | Deutsch |
| `it` | Italiano | Italiano |
| `pt` | Portugués | Português |
| `ru` | Ruso | Русский |
| `zh` | Chino | 中文 |
| `ja` | Japonés | 日本語 |
| `ar` | árabe | العربية |
| Y muchos más... |

Para ver todos los idiomas soportados:
```bash
voxforge voice prepare --help
```

---

## ⚠ Eficiencia y Rendimiento

### Uso de CPU

VoxForge funciona completamente en CPU. La velocidad de sintetización depende de tu hardware:

| Hardware | Velocidad (relativa a tiempo real) |
|----------|-------------------------------------|
| Intel i3-1115G4 (4 core) | ~0.3x - 0.5x (30-50% de tiempo real) |
| Intel i5-12400 (6 core) | ~0.5x - 0.7x (50-70% de tiempo real) |
| Intel i7-13700 (8+ core) | ~0.7x - 0.9x (70-90% de tiempo real) |
| Ryzen 7 5800X (8 core) | ~0.6x - 0.8x (60-80% de tiempo real) |

### Uso de RAM

| Componente | RAM aproximada |
|------------|----------------|
| Modelo XTTS-v2 | ~2-3 GB |
| Procesamiento de audio | ~500 MB - 1 GB |
| Caché de fragmentos | Depende del tamaño del proyecto |

**Nota:** El modelo se carga en memoria solo cuando se necesita y se descarga automáticamente después de 10 minutos de inactividad (configurable).

### Sistema de Caché

VoxForge usa un sistema de caché inteligente que:
- Guarda fragmentos de audio ya sintetizados
- Permite reanudar narraciones interrumpidas
- Evita reprocesar el mismo texto
- Ahorra tiempo y recursos

Para limpiar la caché:
```bash
voxforge cache cleanup

# Limpiar caché de fragmentos individuales
voxforge cache cleanup --fragments

# Limpiar cache de voz
voxforge cache cleanup --voices

# Limpiar todo (fragments + voces + modelos)
voxforge cache cleanup --all
```

---

## ❌ Solución de Problemas

### Problema: No se encuentra el perfil de voz

```bash
Error: No existe el perfil de voz 'mi_voz'
```

**Solución:**
```bash
# Listar perfiles disponibles
voxforge voice list

# Crear un nuevo perfil
voxforge voice record --name mi_voz
```

### Problema: Error al cargar el modelo XTTS

```bash
Error: El modelo no está descargado
```

**Solución:**
```bash
# Descargar modelos
voxforge model download
```

### Problema: El audio suena muy bajo

**Solución:** La normalización EBU R128 ya está aplicada por defecto. Si el audio suena bajo:
- Verifica que `apply_ebu_r128` esté activo en la configuración
- Asegúrate de que la muestra de voz sea clara y con buen nivel

### Problema: La narración se interrumpe

**Solución:** VoxForge guarda el progreso automáticamente. Para reanudar:
```bash
# Reanudar desde el punto de interrupción
voxforge chapter narrate mi_libro 1 --out Capitulo_01.mp3

# O regenerar completamente
voxforge chapter narrate mi_libro 1 --regen --out Capitulo_01.mp3
```

### Problema: Espacio en disco insuficiente

**Solución:**
```bash
# Limpiar cache
voxforge cache cleanup --all

# Cambiar el directorio de cache
voxforge config set cache_dir /ruta/a/disco/grande/cache
```

---

## ⚖ Contribución

¡Las contribuciones son bienvenidas! Por favor sigue estos pasos:

1. Haz un fork del repositorio
2. Crea una rama para tu funcionalidad (`git checkout -b feature/mi-funcionalidad`)
3. Realiza tus cambios
4. Ejecuta las pruebas: `python -m pytest tests/`
5. Realiza el commit de tus cambios (`git commit -m "Añade mi funcionalidad"`)
6. Envía un Pull Request

### Estándares de Código

- PEP 8 (Guía de estilo de Python)
- Type hints obligatorios en funciones públicas
- Nombres de variables y funciones en snake_case
- Nombres de clases en PascalCase
- Docstrings en todas las funciones públicas

### Ejecutar pruebas

```bash
# Todas las pruebas
python -m pytest tests/

# Pruebas específicas
python -m pytest tests/test_core.py

# Con cobertura
python -m pytest tests/ --cov=voxforge
```

---

## ✏ Limpieza

Para limpiar archivos temporales y cache:

```bash
# Limpiar cache
voxforge cache cleanup --all

# Limpiar modelos descargados
voxforge model cleanup

# Eliminar entorno virtual
rm -rf .venv
```

---

## ☺ roadmap

### Versión 0.6.0 (Actual)
- ✅ Capa de servicios centralizada
- ✅ Normalización EBU R128
- ✅ Reanudación de narraciones
- ✅ Soporta más de 15 idiomas

### Versión 0.7.0 (Próximo)
- → Interfaz REST API
- → Soporte para múltiples motores TTS
- → Mejoras en la GUI
- → Documentación completa

### Versión 0.8.0
- → Integración con Voice Engine
- → Soporte para GPU (opcional)
- → Studio mode para grabación profesional

### Versión 1.0.0
- → Versión estable
- → Instalador para todas las plataformas
- → Community support

---

## ❤ Apoyo

Si te gusta VoxForge Local, considera:

- ★ Dar una estrella a este repositorio
- ★ Reportar problemas o solicitar funcionalidades
- ★ Contribuir con código
- ★ Compartir con otros desarrolladores

---

## ⓒ Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.

---

## ✉ Contacto

Para preguntas o soporte, por favor abre un [Issue](https://github.com/tu-usuario/voxforge/issues) en el repositorio.

**Nota:** Este proyecto es de código abierto y no tiene soporte comercial.

---

> ❤ Hecho con amor para la comunidad de audio y voz ❤
