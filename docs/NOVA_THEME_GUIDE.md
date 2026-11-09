# NOVA Premium Theme - Guía de Uso

> **Tema Visual Profesional para VoxForge Local**
> Inspiración: Sistema de Operaciones Cognitivas NOVA

---

## 🎨 Visión General

El **NOVA Premium Theme** es un tema visual de calidad profesional con una estética *cyberpunk* moderna, diseñado específicamente para VoxForge Local. Combina fondos oscuros profundos con acentos eléctricos en azul cian, creando una experiencia visual futurista y elegante que evoca el estilo del sistema NOVA Cognitive Operations System.

### Características Clave

- ✅ **Estética Cyberpunk Profesional**: Diseño inspirado en sistemas de IA de vanguardia
- ✅ **Paleta de Colores NOVA**: Azules eléctricos, negros profundos y acentos luminosos
- ✅ **Compatibilidad Total**: Funciona con PySide6/Qt y CLI
- ✅ **Efectos Visuales**: Gradientes, sombras luminosas y transiciones suaves
- ✅ **Tema Oscuro**: Optimizado para trabajo prolongado sin fatiga visual
- ✅ **Accesibilidad**: Alto contraste y legibilidad en todos los elementos

---

## 📱 Preview Visual

### Paleta de Colores

| Color | Hex | Uso |
|-------|-----|-----|
| **Background Primary** | `#0a0a0f` | Fondo principal de la aplicación |
| **Background Secondary** | `#12121a` | Fondo de paneles principales |
| **Background Tertiary** | `#1a1a25` | Fondo de tarjetas y widgets |
| **Accent Primary** | `#00ffff` | Botones principales, acentos |
| **Accent Secondary** | `#00b4ff` | Botones secundarios |
| **Accent Tertiary** | `#0066cc` | Bordes, seleccionados |
| **Text Primary** | `#e0e0ff` | Texto principal |
| **Text Secondary** | `#a0a0d0` | Texto secundario |

### Componentes Visuales

```
┌─────────────────────────────────────────────────────────┐
│  [NOVA PREMIUM]          ✕ □ ▢                  [⚙️] │  ← Barra de título
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 🎤 Voces   │  │ 📚 Proyectos│  │ ⚙️ Config   │     │  ← Pestañas con gradiente
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Perfil: "María_clara"                              │   │
│  │  ┌─────────────────────────────────────────┐    │   │
│  │  │  ▶️ 00:00 / 03:45  ████████░░░░ 56%      │    │   │
│  │  └─────────────────────────────────────────┘    │   │
│  │                                                     │   │
│  │  [🎙️ Grabando...]  [⏹️ Detener]  [💾 Guardar]    │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  ▶️ Capitulo 1: "Introducción"  ✓ Completo        │   │
│  │  ▶️ Capitulo 2: "Desarrollo"   ▶️ 45%            │   │
│  │  □ Capitulo 3: "Conclusión"                        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
      ↑ Azules eléctricos (#00ffff) en acentos y bordes
      ↑ Negros profundos (#0a0a0f) como fondo
      ↑ Textos claros (#e0e0ff) para máxima legibilidad
```

---

## 🛠️ Instalación y Uso

### Requisitos

- Python 3.10+
- PySide6 6.4+
- VoxForge Local 0.6.0+

### Método 1: Aplicación Automática (Recomendado)

```python
from PySide6.QtWidgets import QApplication
from voxforge.themes import apply_nova_theme

app = QApplication([])

# Aplicar el tema NOVA
apply_nova_theme(app)

# Continuar con la inicialización de tu aplicación
from voxforge.gui import MainWindow
window = MainWindow()
window.show()
app.exec()
```

### Método 2: Aplicación Manual

```python
from PySide6.QtWidgets import QApplication
from voxforge.themes import NOVA_THEME

app = QApplication([])

# Establecer el stylesheet manualmente
app.setStyleSheet(NOVA_THEME)

# Opcional: También aplicar la paleta
from voxforge.themes import create_nova_palette
app.setPalette(create_nova_palette())
```

### Método 3: Para GUI Existente

Si ya tienes una aplicación en funcionamiento, puedes aplicar el tema en cualquier momento:

```python
from voxforge.themes import apply_nova_theme

# Aplicar a la aplicación existente
apply_nova_theme(QApplication.instance())

# O actualizar un widget específico
widget.setStyleSheet(NOVA_THEME)
```

---

## 💻 Uso en CLI

El tema NOVA también incluye colores para la salida en terminal:

### Ejemplo Básico

```python
from voxforge.themes import NOVA_CLI_Theme

# Colores para la terminal
print(NOVA_CLI_Theme.title("VoxForge Local"))
print(NOVA_CLI_Theme.header("=" * 50))
print(NOVA_CLI_Theme.accent("Proceso: ") + NOVA_CLI_Theme.success("Completado"))
print(NOVA_CLI_Theme.warning("Advertencia: ") + "El modelo no está cargado")
print(NOVA_CLI_Theme.error("Error: ") + "Archivo no encontrado")
print(NOVA_CLI_Theme.info("Info: ") + "Procesando capítulo 1...")
```

### Ejemplo en el CLI de VoxForge

Puedes modificar `voxforge/cli.py` para usar los colores NOVA:

```python
from voxforge.themes import NOVA_CLI_Theme

def print_header(text):
    print(NOVA_CLI_Theme.title(f"\n{text}\n"))

def print_success(text):
    print(f"{NOVA_CLI_Theme.success('✓')} {text}")

def print_error(text):
    print(f"{NOVA_CLI_Theme.error('✗')} {text}")

def print_warning(text):
    print(f"{NOVA_CLI_Theme.warning('⚠')} {text}")

def print_info(text):
    print(f"{NOVA_CLI_Theme.info('ℹ')} {text}")
```

---

## 🎨 Personalización

### Acceso a Colores Individuales

Puedes acceder a los colores definidos directamente:

```python
from voxforge.themes import (
    NOVA_ACCENT_PRIMARY,
    NOVA_ACCENT_SECONDARY,
    NOVA_BG_PRIMARY,
    NOVA_BG_SECONDARY,
    NOVA_TEXT_PRIMARY,
    NOVA_TEXT_SECONDARY,
)

# Usar en tu código
button.setStyleSheet(f"""
    QPushButton {{
        background-color: {NOVA_ACCENT_PRIMARY};
        color: {NOVA_BG_PRIMARY};
        border: 2px solid {NOVA_ACCENT_SECONDARY};
    }}
""")
```

### Crear Componentes Personalizados

```python
from voxforge.themes import NOVA_ACCENT_PRIMARY, NOVA_BG_TERTIARY

# Botón con estilo NOVA
custom_button_style = f"""
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {NOVA_ACCENT_PRIMARY},
        stop:1 #0066cc);
    color: white;
    border: 2px solid {NOVA_ACCENT_PRIMARY};
    border-radius: 8px;
    padding: 10px 24px;
    font-weight: 600;
    transition: all 0.3s ease;
}}

QPushButton:hover {{
    box-shadow: 0 0 20px {NOVA_ACCENT_PRIMARY};
}}
"""

button.setStyleSheet(custom_button_style)
```

### Extender el Tema

Puedes crear tu propio tema basado en NOVA:

```python
from voxforge.themes.nova_premium import (
    NOVA_BG_PRIMARY,
    NOVA_ACCENT_PRIMARY,
    NOVA_TEXT_PRIMARY,
)

CUSTOM_THEME = f"""
/* Heredar de NOVA pero con cambios */
QWidget {{
    background-color: {NOVA_BG_PRIMARY};
    color: {NOVA_TEXT_PRIMARY};
}}

/* Añadir tus estilos personalizados */
MyCustomWidget {{
    background: {NOVA_ACCENT_PRIMARY};
    color: white;
}}
"""
```

---

## 📋 Estructura del Tema

### Archivos del Tema

```
voxforge/
├── themes/
│   ├── __init__.py          # Exporta todo el módulo
│   └── nova_premium.py      # Definición completa del tema
│
└── docs/
    └── NOVA_THEME_GUIDE.md   # Esta guía
```

### Contenido de `nova_premium.py`

1. **Paleta de Colores**: Definición de todos los colores HEX
2. **Gradientes**: Definiciones de gradientes para botones y paneles
3. **NOVA_THEME**: Stylesheet QSS completo para todos los widgets
4. **NOVA_CLI_Theme**: Clase para colores ANSI en terminal
5. **Funciones de Utilidad**: `apply_nova_theme()`, `create_nova_palette()`
6. **Metadata**: Información del tema

---

## 🔧 Componentes Estilizados

El tema NOVA estilizada todos los widgets principales de Qt:

### ✅ Controles Básicos
- `QApplication` - Aplicación base
- `QWidget` - Widget genérico
- `QLabel` - Etiquetas (con variantes: accent, success, warning, error)
- `QPushButton` - Botones (con variantes: primary, accent, danger)
- `QToolButton` - Botones de herramientas

### ✅ Entrada de Datos
- `QLineEdit` - Campos de texto
- `QTextEdit` - Áreas de texto
- `QPlainTextEdit` - Áreas de texto simples
- `QComboBox` - Selectores desplegables
- `QSpinBox` / `QDoubleSpinBox` - Selectores numéricos

### ✅ Selección
- `QCheckBox` - Casillas de verificación
- `QRadioButton` - Botones de radio
- `QSlider` - Controles deslizantes

### ✅ Contenedores
- `QGroupBox` - Grupos con bordes
- `QFrame` - Marcos
- `QTabWidget` - Pestañas
- `QScrollBar` - Barras de desplazamiento

### ✅ Visualización
- `QProgressBar` - Barras de progreso
- `QHeaderView` - Cabeceras de tablas
- `QTableView` / `QTreeView` - Tablas y árboles

### ✅ Menús
- `QMenuBar` - Barra de menú
- `QMenu` - Menús desplegables
- `QStatusBar` - Barra de estado

### ✅ Diálogos y ToolTips
- `QToolTip` - Tooltips
- `QMessageBox` - Cajas de mensaje (heredan estilos)

### ✅ Widgets Específicos de VoxForge
- `voice_card` - Tarjetas de perfil de voz
- `project_card` - Tarjetas de proyecto
- `waveform` - Visualización de forma de onda
- `player_controls` - Controles del reproductor
- `progress_indicator` - Indicador de progreso

---

## 🎯 Estilo de Diseño NOVA

### Principios de Diseño

1. **Jerarquía Visual**: Uso de colores para guiar la atención
   - **Azul Eléctrico (#00ffff)**: Elementos principales y acciones
   - **Azul Secundario (#00b4ff)**: Elementos secundarios
   - **Gris Claros (#e0e0ff)**: Texto y contenido

2. **Profundidad**: Creación de capas con colores de fondo
   - Capa 1 (Fondo): `#0a0a0f` - Espacio profundo
   - Capa 2 (Panel): `#12121a` - Paneles principales
   - Capa 3 (Tarjeta): `#1a1a25` - Tarjetas y widgets
   - Capa 4 (Elevado): `#202030` - Elementos elevados

3. **Feedback Visual**: Transiciones y efectos
   - Todos los botones tienen efecto hover con sombra luminosa
   - Los campos de entrada tienen bordes que brillan al enfocarse
   - Las tarjetas tienen un ligero brillo al pasar el cursor

4. **Consistencia**: Patrones repetidos
   - Bordes redondeados (8px para la mayoría, 6px para elementos pequeños)
   - Anchos de borde consistentes (2px para bordes principales)
   - Transiciones suaves (0.3s)

### Buenas Prácticas

✅ **DO:**
- Usa los colores definidos para mantener la coherencia
- Aplica el tema a toda la aplicación, no solo a widgets individuales
- Usa los estilos predefinidos para botones y controles
- Mantén el contraste alto para la accesibilidad

❌ **DON'T:**
- No combines temas (NOVA + otro tema)
- No modifiques los colores base sin necesidad
- No elimines las transiciones (dan fluidez al tema)
- No uses colores que no estén en la paleta NOVA

---

## 🔬 Testing del Tema

### Verificar que el Tema Funciona

```python
# Test básico de importación
python3 -c "from voxforge.themes import NOVA_THEME; print('OK')"

# Test de aplicación
python3 -c ""
from PySide6.QtWidgets import QApplication
from voxforge.themes import apply_nova_theme
import sys

app = QApplication(sys.argv)
apply_nova_theme(app)
print('Theme applied successfully!')
"
```

### Verificar Colores

```python
from voxforge.themes import NOVA_CLI_Theme

# Mostrar paleta de colores en terminal
print(f"Primary:    {NOVA_CLI_Theme.PRIMARY}■{NOVA_CLI_Theme.RESET}")
print(f"Secondary:  {NOVA_CLI_Theme.SECONDARY}■{NOVA_CLI_Theme.RESET}")
print(f"Text:       {NOVA_CLI_Theme.TEXT}■{NOVA_CLI_Theme.RESET}")
print(f"Success:    {NOVA_CLI_Theme.success('✓')}")
print(f"Warning:    {NOVA_CLI_Theme.warning('⚠')}")
print(f"Error:      {NOVA_CLI_Theme.error('✗')}")
```

---

## 📚 Referencia Rápida

### Colores Principales

```python
from voxforge.themes import (
    NOVA_ACCENT_PRIMARY,   # #00ffff - Azul eléctrico
    NOVA_ACCENT_SECONDARY, # #00b4ff - Azul claro
    NOVA_BG_PRIMARY,       # #0a0a0f - Negro profundo
    NOVA_BG_SECONDARY,     # #12121a - Negro medio
    NOVA_TEXT_PRIMARY,     # #e0e0ff - Blanco suave
)
```

### Funciones de Utilidad

```python
from voxforge.themes import (
    apply_nova_theme,      # Aplica tema a QApplication
    create_nova_palette,   # Crea QPalette para NOVA
    NOVA_THEME,            # Stylesheet completo
    NOVA_THEME_INFO,       # Metadata del tema
)
```

### Tema CLI

```python
from voxforge.themes import NOVA_CLI_Theme

NOVA_CLI_Theme.title("Título")      # Texto con estilo de título
NOVA_CLI_Theme.header("Encabezado") # Texto con estilo de encabezado
NOVA_CLI_Theme.accent("Acento")     # Texto con color de acento
NOVA_CLI_Theme.success("Éxito")     # Texto de éxito (verde)
NOVA_CLI_Theme.warning("Advertencia")# Texto de advertencia (amarillo)
NOVA_CLI_Theme.error("Error")       # Texto de error (rojo)
NOVA_CLI_Theme.info("Info")         # Texto informativo (azul)
```

---

## 🎓 Ejemplo Completo

Aquí tienes un ejemplo completo de una aplicación con el tema NOVA:

```python
#!/usr/bin/env python3
"""Ejemplo de aplicación con tema NOVA."""

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QPushButton, QLabel, QLineEdit, QProgressBar
)
from voxforge.themes import apply_nova_theme, NOVA_CLI_Theme


class DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NOVA Theme Demo")
        self.setGeometry(100, 100, 600, 400)
        
        # Widget principal
        central_widget = QWidget()
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # Añadir widgets
        layout.addWidget(QLabel("NOVA Premium Theme Demo"))
        layout.addWidget(QLineEdit("Campo de texto con estilo NOVA"))
        layout.addWidget(QPushButton("Botón Primario"))
        layout.addWidget(QPushButton("Botón Secundario"))
        layout.addWidget(QProgressBar())
        
        # Aplicar propiedades
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)


def main():
    app = QApplication(sys.argv)
    
    # Aplicar tema NOVA
    apply_nova_theme(app)
    
    # Mostrar mensaje en terminal
    print(NOVA_CLI_Theme.title("NOVA Theme Demo"))
    print(NOVA_CLI_Theme.success("Theme aplicado correctamente!"))
    
    # Crear y mostrar ventana
    window = DemoWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

---

## 🐛 Solución de Problemas

### El tema no se aplica

**Problema:** Los widgets no muestran el estilo NOVA.

**Soluciones:**
1. Asegúrate de llamar a `apply_nova_theme(app)` **antes** de crear cualquier widget
2. Verifica que la aplicación Qt esté inicializada
3. Comprueba que no haya otros estilosheets aplicados después

### Colores incorrectos en terminal

**Problema:** Los colores ANSI no se muestran correctamente.

**Soluciones:**
1. Asegúrate de que tu terminal soporte colores ANSI (la mayoría lo hacen)
2. En Windows, habilita el soporte ANSI en las propiedades de la terminal
3. Prueba con: `python3 -c "print('\033[36mTest\033[0m')"`

### Problemas de rendimiento

**Problema:** La aplicación se siente lenta con el tema aplicado.

**Soluciones:**
1. El tema NOVA está optimizado, pero las transiciones pueden afectar el rendimiento
2. Si es necesario, puedes deshabilitar transiciones modificando el stylesheet
3. Considera usar una versión simplificada para hardware antiguo

---

## 📖 Inspiración

El tema NOVA está inspirado en:
- **NOVA Cognitive Operations System** - Sistema de IA futurista
- **Cyberpunk 2077** - Estética neon y tecnológica
- **Tron Legacy** - Diseño luminoso y digital
- **Terminal de Linux Moderno** - Claridad y legibilidad

---

## 🎉 Conclusión

El **NOVA Premium Theme** transformará tu experiencia con VoxForge Local, dándole un aspecto profesional y futurista que combina perfectamente con la funcionalidad de clonación de voz de vanguardia del software.

Con este tema, cada interacción con VoxForge sentirá como estar trabajando con una herramienta de alta tecnología, digna de un estudio profesional.

---

**¡Disfruta de tu nueva experiencia visual con NOVA!** 🚀

*"Aquí las ideas no se quedan en teoría... se convierten en realidad."* - NOVA
