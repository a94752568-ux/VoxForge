# VoxForge Local

> **Estudio de clonaci\u00f3n de voz y narraci\u00f3n 100% local/offline en Python**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Status: Beta](https://img.shields.io/badge/status-Beta-yellow.svg)]()

---

## \u2728 Descripci\u00f3n

**VoxForge Local** es un estudio completo para la creaci\u00f3n de audiolibros y narraciones con **clonaci\u00f3n de voz 100% local**. No requiere conexi\u00f3n a Internet, no env\u00eda datos a la nube, y funciona \u00fanicamente con la potencia de tu CPU.

**Caracter\u00edsticas principales:**

- \u2705 **Clonaci\u00f3n de voz multiling\u00fce** con Coqui XTTS-v2
- \u2705 **S\u00edntesis de voz natural** en m\u00e1s de 15 idiomas
- \u2705 **Gesti\u00f3n de proyectos** con cap\u00adtulos organizados
- \u2705 **Normalizaci\u00f3n EBU R128** para calidad de estudio profesional
- \u2705 **Sistema de cach\u00e9 inteligente** para reanudar narraciones interrumpidas
- \u2705 **Interfaz CLI y GUI** con PySide6
- \u2705 **100% offline** - Todo el procesamiento se realiza localmente
- \u2705 **Solo CPU** - Compatible con sistemas sin GPU

---

## \u26a1 Requisitos del Sistema

| Requisito | M\u00ednimo | Recomendado |
|-----------|------------|-------------|
| **Sistema Operativo** | Linux, Windows, macOS | Linux (Ubuntu 22.04+) |
| **Python** | 3.10 | 3.11+ |
| **RAM** | 8 GB | 16 GB |
| **CPU** | 4 n\u00facleos | 8+ n\u00facleos (Intel i5/i7/Ryzen) |
| **Almacenamiento** | 5 GB libres | 20 GB libres (para modelos y cach\u00e9) |
| **GPU** | No requerida | No requerida (funciona solo con CPU) |

---

## \u2308 Instalaci\u00f3n

### Opci\u00f3n 1: Instalaci\u00f3n con pipx (Recomendado)

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

### Opcion 2: Instalacion con pip

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

### Opcion 3: Descarga de modelos

Los modelos de XTTS-v2 se descargan automaticamente la primera vez que los usas:

```bash
voxforge model download
```

---

## \u2680 Uso R\u00e1pido

### 1. Crear un perfil de voz

Primero, graba una muestra de tu voz (recomendado: 1-5 minutos de audio claro):

```bash
# Grabacion directa (el programa te guiara)
voxforge voice record --name mi_voz

# O usando un archivo WAV existente
voxforge voice add mi_voz /ruta/a/tu/muestra.wav --language es
```

### 2. Crear un proyecto

```bash
voxforge project create mi_libro --voice mi_voz --language es
```

### 3. A\u00f1adir un cap\u00edtulo

```bash
# Desde un archivo de texto
voxforge chapter add mi_libro 1 --file capitulo1.txt

# Desde un PDF (se extraera el texto automaticamente)
voxforge chapter add mi_libro 2 --file capitulo2.pdf

# Desde DOCX, EPUB, MD
voxforge chapter add mi_libro 3 --file capitulo3.docx
```

### 4. Narrar un cap\u00edtulo

```bash
# Narrar con la voz clonada
voxforge chapter narrate mi_libro 1 --out Capitulo_01.mp3

# Narrar con normalizacion EBU R128 (calidad de estudio)
voxforge chapter narrate mi_libro 1 --out Capitulo_01.mp3

# Narrar con efectos de voz (opcional)
voxforge chapter narrate mi_libro 1 --fx warm --out Capitulo_01.mp3
```

### 5. Narrar un proyecto completo

```bash
# Narrar todos los capitulos de un proyecto
voxforge project-narrate mi_libro --out-dir audiobook/

# Con formato WAV (sin compresion)
voxforge project-narrate mi_libro --format wav --out-dir audiobook/

# Con formato FLAC (calidad alta, compresion sin perdida)
voxforge project-narrate mi_libro --format flac --out-dir audiobook/
```

---

## \u2753 Interfaz Gr\u00e1fica

Para iniciar la interfaz gr\u00e1fica:

```bash
# Con pipx
voxforge-gui

# Con Python
python -m gui

# O directamente
python gui.py
```

La interfaz gr\u00e1fica ofrece:
- Gesti\u00f3n visual de proyectos y cap\u00edtulos
- Grabaci\u00f3n de voz integrada
- Reproducci\u00f3n de audio
- Monitoreo del progreso de narraci\u00f3n
- Configuraci\u00f3n de efectos de voz

---

## \u2699 Configuraci\u00f3n

### Archivo de configuraci\u00f3n

La configuraci\u00f3n se guarda en `~/.voxforge/config.json` (Linux/macOS) o `%APPDATA%\voxforge\config.json` (Windows).

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

### Opciones de configuraci\u00f3n

| Opcion | Tipo | Descripci\u00f3n | Valor por defecto |
|--------|------|------------------|-------------------|
| `language` | string | Idioma por defecto | "es" |
| `voice_profile` | string | Perfil de voz por defecto | "yo_limpia" |
| `sample_rate` | int | Frecuencia de muestreo | 24000 |
| `apply_ebu_r128` | bool | Aplicar normalizacion EBU R128 | true |
| `cache_dir` | string | Directorio de cache | "data/cache" |
| `export_dir` | string | Directorio de exportaci\u00f3n | "data/exports" |
| `max_retries` | int | Maximos reintentos de sintetizacion | 3 |
| `auto_unload` | bool | Descargar modelo automaticamente | true |
| `auto_unload_minutes` | int | Minutos de inactividad antes de descargar | 10 |

---

## \u272f Idiomas Soportados

| C\u00f3digo | Idioma | Nombre nativo |
|-------|--------|----------------|
| `es` | Espa\u00f1ol | Espa\u00f1ol |
| `en` | Ingl\u00e9s | English |
| `fr` | Franc\u00e9s | Fran\u00e7ais |
| `de` | Alem\u00e1n | Deutsch |
| `it` | Italiano | Italiano |
| `pt` | Portugu\u00e9s | Portugu\u00eas |
| `ru` | Ruso | \u0420\u0443\u0441\u0441\u043a\u0438\u0439 |
| `zh` | Chino | \u4e2d\u6587 |
| `ja` | Japon\u00e9s | \u65e5\u672c\u8a9e |
| `ar` | \u00e1rabe | \u0627\u0644\u0639\u0631\u0628\u064a\u0629 |
| Y muchos m\u00e1s... |

Para ver todos los idiomas soportados:
```bash
voxforge voice prepare --help
```

---

## \u26a0 Eficiencia y Rendimiento

### Uso de CPU

VoxForge funciona completamente en CPU. La velocidad de sintetizaci\u00f3n depende de tu hardware:

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
| Cach\u00e9 de fragmentos | Depende del tama\u00f1o del proyecto |

**Nota:** El modelo se carga en memoria solo cuando se necesita y se descarga automaticamente despu\u00e9s de 10 minutos de inactividad (configurable).

### Sistema de Cach\u00e9

VoxForge usa un sistema de cach\u00e9 inteligente que:
- Guarda fragmentos de audio ya sintetizados
- Permite reanudar narraciones interrumpidas
- Evita reprocesar el mismo texto
- Ahorra tiempo y recursos

Para limpiar la cach\u00e9:
```bash
voxforge cache cleanup

# Limpiar cache de fragmento individuales
voxforge cache cleanup --fragments

# Limpiar cache de voz
voxforge cache cleanup --voices

# Limpiar todo (fragments + voces + modelos)
voxforge cache cleanup --all
```

---

## \u274c Soluci\u00f3n de Problemas

### Problema: No se encuentra el perfil de voz

```bash
Error: No existe el perfil de voz 'mi_voz'
```

**Soluci\u00f3n:**
```bash
# Listar perfiles disponibles
voxforge voice list

# Crear un nuevo perfil
voxforge voice record --name mi_voz
```

### Problema: Error al cargar el modelo XTTS

```bash
Error: El modelo no est\u00e1 descargado
```

**Soluci\u00f3n:**
```bash
# Descargar modelos
voxforge model download
```

### Problema: El audio suena muy bajo

**Soluci\u00f3n:** La normalizacion EBU R128 ya esta aplicada por defecto. Si el audio suena bajo:
- Verifica que `apply_ebu_r128` este activo en la configuracion
- Asegurate de que la muestra de voz sea clara y con buen nivel

### Problema: La narraci\u00f3n se interrumpe

**Soluci\u00f3n:** VoxForge guarda el progreso automaticamente. Para reanudar:
```bash
# Reanudar desde el punto de interrupci\u00f3n
voxforge chapter narrate mi_libro 1 --out Capitulo_01.mp3

# O regenerar completamente
voxforge chapter narrate mi_libro 1 --regen --out Capitulo_01.mp3
```

### Problema: Espacio en disco insuficiente

**Soluci\u00f3n:**
```bash
# Limpiar cache
voxforge cache cleanup --all

# Cambiar el directorio de cache
voxforge config set cache_dir /ruta/a/disco/grande/cache
```

---

## \u2696 Contribuci\u00f3n

¡Las contribuciones son bienvenidas! Por favor sigue estos pasos:

1. Haz un fork del repositorio
2. Crea una rama para tu funcionalidad (`git checkout -b feature/mi-funcionalidad`)
3. Realiza tus cambios
4. Ejecuta las pruebas: `python -m pytest tests/`
5. Realiza el commit de tus cambios (`git commit -m "A\u00f1ade mi funcionalidad"`)
6. Env\u00eda un Pull Request

### Est\u00e1ndares de C\u00f3digo

- PEP 8 (Gu\u00eda de estilo de Python)
- Type hints obligatorios en funciones p\u00fablicas
- Nombres de variables y funciones en snake_case
- Nombres de clases en PascalCase
- Docstrings en todas las funciones p\u00fablicas

### Ejecutar pruebas

```bash
# Todas las pruebas
python -m pytest tests/

# Pruebas especificas
python -m pytest tests/test_core.py

# Con cobertura
python -m pytest tests/ --cov=voxforge
```

---

## \u270f Limpieza

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

## \u263a roadmap

### Versi\u00f3n 0.6.0 (Actual)
- \u2705 Capa de servicios centralizada
- \u2705 Normalizaci\u00f3n EBU R128
- \u2705 Reanudaci\u00f3n de narraciones
- \u2705 Soporta m\u00e1s de 15 idiomas

### Versi\u00f3n 0.7.0 (Pr\u00f3ximo)
- \u2192 Interfaz REST API
- \u2192 Soporte para m\u00faltiples motores TTS
- \u2192 Mejoras en la GUI
- \u2192 Documentaci\u00f3n completa

### Versi\u00f3n 0.8.0
- \u2192 Integracion con Voice Engine
- \u2192 Soporte para GPU (opcional)
- \u2192 Studio mode para grabacion profesional

### Versi\u00f3n 1.0.0
- \u2192 Versi\u00f3n estable
- \u2192 Instalador para todas las plataformas
- \u2192 Community support

---

## \u2764 Apoyo

Si te gusta VoxForge Local, considera:

- \u2605 Dar una estrella a este repositorio
- \u2605 Reportar problemas o solicitar funcionalidades
- \u2605 Contribuir con c\u00f3digo
- \u2605 Compartir con otros desarrolladores

---

## \u24d2 Licencia

Este proyecto est\u00e1 bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para m\u00e1s detalles.

---

## \u2709 Contacto

Para preguntas o soporte, por favor abre un [Issue](https://github.com/tu-usuario/voxforge/issues) en el repositorio.

**Nota:** Este proyecto es de c\u00f3digo abierto y no tiene soporte comercial.

---

> \u2764 Hecho con amor para la comunidad de audio y voz \u2764
