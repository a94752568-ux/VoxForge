# VoxForge — UI Cyberpunk (Night City)

Módulos de interfaz gráfica con estilo cyberpunk para VoxForge, el estudio de
narración local 100% offline (XTTS-v2, CPU-only).

## Estructura

```
voxforge/ui/
├── __init__.py      # Exportaciones del paquete
├── theme.py         # Paleta de colores y QSS Night City
├── widgets.py       & Widgets personalizados (NeonProgressBar, PulseChip,
│                     WaveformWidget, FragmentCard, CyberPanel)
└── main_window.py   # Ventana principal con layout de 3 columnas
```

## Paleta de colores

| Variable | Valor | Uso |
|----------|-------|-----|
| `BG` | `#05060F` | Fondo principal |
| `PANEL` | `#0B0F22` | Paneles principales |
| `PANEL_2` | `#0D1226` | Paneles secundarios |
| `PANEL_3` | `#151B33` | Tarjetas / contenedores |
| `CYAN` | `#00F0FF` | Acento principal |
| `MAGENTA` | `#FF2A6D` | Acento secundario |
| `PURPLE` | `#B967FF` | Morado neón |
| `AMBER` | `#FFB000` | Ámbar / advertencia |
| `GREEN` | `#00FF9C` | Verde éxito / activo |
| `TEXT` | `#D6E6FF` | Texto principal |
| `MUTED` | `#7A8DB5` | Texto tenue |

## Widgets disponibles

### `NeonProgressBar`
Barra de progreso con gradiente cian → magenta, escaneo de luz animado, y texto
con % + frag/s + ETA en vivo.

```python
bar = NeonProgressBar()
bar.set_progress_info(45, frag_s=2.3, eta_text="2m 15s")
bar.start_scan()   # Inicia animación de escaneo
bar.stop_scan()    # Detiene animación
```

### `PulseChip`
Etiqueta con punto que late para estados (EN CURSO, CPU, voces).

```python
chip = PulseChip("SISTEMA · LISTO", CYAN)
chip.set_status("EN CURSO", MAGENTA)
```

### `WaveformWidget`
Onda animada al reproducir/narrar.

```python
wave = WaveformWidget()
wave.start()   # Inicia animación
wave.stop()    # Detiene y deja en reposo
```

### `FragmentCard`
Tarjeta de fragmento con número, título, subtítulo y chip opcional "PAUSA".

```python
card = FragmentCard("01", "LA RAZA CÓSMICA", "15 caracteres", is_pause=False)
card.set_pause(True)  # Cambia a modo pausa (borde ámbar)
```

### `CyberPanel`
Panel con borde y efecto de resplandor (glow) real vía `QGraphicsDropShadowEffect`.

```python
panel = CyberPanel(glow_color=CYAN, blur=18)
```

## Ventana principal (`MainWindow`)

Layout de 3 columnas:
1. **Izquierda**: Proyectos / Capítulos / Flujo de trabajo
2. **Centro**: Proyecto activo + Fragmentos
3. **Derecha**: Trabajos / Registro
4. **Abajo**: Reproductor de audio con barra de progreso y controles

```python
from voxforge.ui.main_window import MainWindow

window = MainWindow()
window.show()
```

## Cómo integrar con tu motor real

Hay **2 puntos TODO** marcados en `main_window.py` donde debes enchufar tu lógica existente:

### TODO 1 — Conectar botones a acciones

En `MainWindow`, los botones existen pero sus señales no están conectadas a tu lógica.
Conéctalos en `__init__` o en un método separado:

```python
# Ejemplo:
self.btn_import.clicked.connect(self.action_import_book)
self.btn_play.clicked.connect(self.action_play)
self.btn_stop.clicked.connect(self.action_stop)
```

### TODO 2 — Conectar datos reales a los widgets

Los datos mostrados son de demostración. Conéctalos a tu modelo de datos:

```python
# Ejemplo: actualizar progreso de un trabajo real
self.j_bar.set_progress_info(
    value=progreso_porcentaje,
    frag_s=fragmentos_por_segundo,
    eta_text="00:02:15"
)

# Ejemplo: actualizar lista de fragmentos con datos reales
for frag in mis_fragmentos:
    card = FragmentCard(frag.numero, frag.titulo, frag.subtitulo, is_pause=frag.es_pausa)
    ...
```

## Cómo correr

```bash
# Desde la raíz del proyecto VoxForge
cd /home/aegis2/VoxForge
source .venv/bin/activate

# Ejecutar la ventana de demostración
python3 -m voxforge.ui.main_window
```

## Verificación

```bash
# Compilar todos los módulos
python3 -m py_compile voxforge/ui/theme.py voxforge/ui/widgets.py voxforge/ui/main_window.py voxforge/ui/__init__.py
```

## Limitaciones conocidas (no probadas en vivo)

- No se ha probado con el motor XTTS-v2 real integrado; los datos son de demostración.
- Las señales de los botones no están conectadas a la lógica de narración existente.
- No se ha probado en un entorno sin `voxforge` instalado como paquete (se asume `PYTHONPATH` o instalación en modo editable).

## Requisitos

- Python 3.9+
- PySide6
- soundfile (para validación de audio en `utils.py`)
- numpy (para `WaveformWidget`)

No se requieren conexiones a internet, claves de API, ni servicios externos.