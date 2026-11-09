# 🎨 NOVA Premium Theme

> **Tema visual premium para VoxForge Local**
> Inspiración: NOVA Cognitive Operations System

---

## 📌 **Vista Rápida**

El **NOVA Premium Theme** es un tema visual de calidad profesional con estética *cyberpunk* para VoxForge Local. Proporciona una experiencia visual elegante y moderna con:

- ✨ **Azules eléctricos** como colores de acento
- 🌑 **Fondos oscuros profundos** para trabajo prolongado
- 🎯 **Alto contraste** para máxima legibilidad
- ✨ **Efectos visuales** (gradientes, sombras, transiciones)

---

## 🛠️ **Instalación**

El tema ya está incluido en el paquete `voxforge`. No se requiere instalación adicional.

---

## 🚀 **Uso Básico**

### **Para GUI (PySide6/Qt)**

```python
from PySide6.QtWidgets import QApplication
from voxforge.themes import apply_nova_theme

app = QApplication([])
apply_nova_theme(app)  # Aplica el tema a toda la aplicación

# Continúa con tu aplicación...
```

### **Para CLI (Terminal)**

```python
from voxforge.themes import NOVA_CLI_Theme

print(NOVA_CLI_Theme.title("VoxForge Local"))
print(NOVA_CLI_Theme.success("✓ Operación completada"))
print(NOVA_CLI_Theme.error("✗ Error: Archivo no encontrado"))
```

---

## 📁 **Estructura**

```
voxforge/themes/
├── __init__.py          # Exporta el módulo
├── nova_premium.py      # Definición del tema
└── README.md            # Este archivo
```

---

## 🎨 **Personalización**

### **Acceso a Colores**

```python
from voxforge.themes import (
    NOVA_ACCENT_PRIMARY,   # #00ffff
    NOVA_ACCENT_SECONDARY, # #00b4ff
    NOVA_BG_PRIMARY,       # #0a0a0f
    NOVA_BG_SECONDARY,     # #12121a
    NOVA_TEXT_PRIMARY,     # #e0e0ff
)

# Usar en estilos personalizados
button.setStyleSheet(f"background-color: {NOVA_ACCENT_PRIMARY};")
```

### **Crear Estilos Personalizados**

```python
from voxforge.themes import NOVA_ACCENT_PRIMARY, NOVA_BG_TERTIARY

custom_style = f"""
QWidget {{
    background-color: {NOVA_BG_TERTIARY};
    color: white;
}}

QPushButton {{
    background: {NOVA_ACCENT_PRIMARY};
    border-radius: 8px;
}}
"""
```

---

## 📖 **Documentación Completa**

Para una guía detallada, consulta:

- 📄 **[Guía Completa de NOVA Theme](https://github.com/your-repo/voxforge/blob/main/docs/NOVA_THEME_GUIDE.md)**
- 🎯 **[Ejemplo GUI](https://github.com/your-repo/voxforge/blob/main/examples/nova_theme_demo.py)**
- 💻 **[Ejemplo CLI](https://github.com/your-repo/voxforge/blob/main/examples/nova_cli_demo.py)**

---

## 🎯 **Características**

### **Soportado en GUI**

✅ Todos los widgets estándar de Qt:
- Botones (con variantes: primary, accent, danger)
- Campos de texto (QLineEdit, QTextEdit)
- Selectores (QComboBox, QSpinBox)
- Controles (QCheckBox, QRadioButton, QSlider)
- Contenedores (QGroupBox, QFrame, QTabWidget)
- Visualización (QProgressBar, QTableView)
- Menús (QMenuBar, QMenu, QStatusBar)

### **Soportado en CLI**

✅ Métodos de estilo:
- `title()` - Títulos importantes
- `header()` - Encabezados
- `accent()` - Texto con acento
- `success()` - Mensajes de éxito ✓
- `warning()` - Advertencias ⚠
- `error()` - Errores ✗
- `info()` - Información ℹ
- `muted()` - Texto secundario
- `bold()` - Negrita
- `dim()` - Tenue

---

## 📊 **Paleta de Colores**

| Color | Hex | Uso |
|-------|-----|-----|
| `NOVA_BG_PRIMARY` | `#0a0a0f` | Fondo principal |
| `NOVA_BG_SECONDARY` | `#12121a` | Fondo de paneles |
| `NOVA_BG_TERTIARY` | `#1a1a25` | Fondo de tarjetas |
| `NOVA_ACCENT_PRIMARY` | `#00ffff` | ✨ Botones principales |
| `NOVA_ACCENT_SECONDARY` | `#00b4ff` | Botones secundarios |
| `NOVA_ACCENT_TERTIARY` | `#0066cc` | Bordes, seleccionados |
| `NOVA_TEXT_PRIMARY` | `#e0e0ff` | Texto principal |
| `NOVA_TEXT_SECONDARY` | `#a0a0d0` | Texto secundario |
| `NOVA_SUCCESS` | `#00ff88` | Estados de éxito |
| `NOVA_WARNING` | `#ffaa00` | Advertencias |
| `NOVA_ERROR` | `#ff3366` | Errores |

---

## 🔧 **Funciones de Utilidad**

| Función | Descripción |
|---------|-------------|
| `apply_nova_theme(app)` | Aplica el tema a una aplicación Qt |
| `create_nova_palette()` | Crea una QPalette con colores NOVA |
| `NOVA_THEME` | Stylesheet QSS completo |
| `NOVA_THEME_INFO` | Metadata del tema |

---

## 🎨 **Preview Visual**

```
┌─────────────────────────────────────────────────────────┐
│  🎙️  VOXFORGE LOCAL                    v0.6.0    ⚙️   │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐                      │
│  │ 🎤 María    │  │ 📚 Proyecto │                      │
│  │  ▶️ 00:00   │  │  ████░░ 56%│                      │
│  │  [✓][✏][🗑]│  │ [▶][✏][💾]│                      │
│  └─────────────┘  └─────────────┘                      │
│                                                         │
│  Fondo: #0a0a0f                                         │
│  Acentos: #00ffff ✨                                     │
│  Textos: #e0e0ff                                        │
└─────────────────────────────────────────────────────────┘
```

---

## 🏆 **Beneficios**

- ✅ **Estética Profesional**: Diseño inspirado en sistemas de IA de vanguardia
- ✅ **Experiencia Mejorada**: Jerarquía visual clara y feedback intuitivo
- ✅ **Alto Contraste**: Fácil lectura en cualquier condición
- ✅ **Consistencia**: Mismo estilo en toda la aplicación
- ✅ **Flexible**: Fácil de personalizar y extender
- ✅ **Rendimiento**: Optimizado para hardware limitado

---

## 📝 **Inspiración**

El tema NOVA está inspirado en:
- **NOVA Cognitive Operations System** - Inteligencia Local, Infinitas Posibilidades
- **Cyberpunk 2077** - Estética neon y tecnológica
- **Tron Legacy** - Diseño digital y luminoso
- **Terminales Modernas** - Claridad y legibilidad

---

## 🤝 **Contribución**

Las contribuciones son bienvenidas:

1. Reporta problemas en el repositorio
2. Sugiere mejoras de diseño
3. Crea nuevos temas basados en NOVA

---

## 📄 **Licencia**

Este tema forma parte de VoxForge Local y se distribuye bajo la misma licencia (MIT).

---

**✨ ¡Disfruta de tu experiencia NOVA Premium! ✨**

> *"Aquí las ideas no se quedan en teoría... se convierten en realidad."*
> — NOVA Cognitive Operations System
