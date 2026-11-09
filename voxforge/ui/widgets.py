"""
widgets.py — Widgets personalizados estilo Night City para VoxForge.

Componentes:
- NeonProgressBar: barra con gradiente cian→magenta, escaneo de luz, % + frag/s + ETA.
- PulseChip: punto que late para estados (EN CURSO / CPU / voces).
- WaveformWidget: onda animada al reproducir/narrar.
- FragmentCard: tarjeta de fragmento (pausa = borde ámbar + chip PAUSA).
- CyberPanel: panel con glow real vía QGraphicsDropShadowEffect.

Solo PySide6 + stdlib. Sin imágenes externas.
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .theme import PALETTE

CYAN = PALETTE["cyan"]
MAGENTA = PALETTE["magenta"]
PURPLE = PALETTE["purple"]
AMBER = PALETTE["amber"]
GREEN = PALETTE["green"]
TEXT = PALETTE["text"]
MUTED = PALETTE["muted"]
BG = PALETTE["bg"]
PANEL = PALETTE["panel"]
PANEL_3 = PALETTE["panel3"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UTILIDAD: GLOW EFECTO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def apply_glow(widget: QWidget, color: QColor, blur: int = 18) -> None:
    """Aplica un efecto de resplandor (glow) a un widget."""
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blur)
    effect.setColor(color)
    effect.setOffset(0, 0)
    widget.setGraphicsEffect(effect)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NEON PROGRESS BAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class NeonProgressBar(QProgressBar):
    """
    Barra de progreso estilo cyberpunk con:
    - Gradiente cian → magenta
    - Escaneo de luz (scan line) que se desplaza
    - Texto con % + frag/s + ETA en vivo
    - Animación de pulso cuando está en indeterminado
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(True)
        self.setMinimumHeight(22)
        self.setMaximumHeight(22)

        # Animación de escaneo de luz
        self._scan_pos = -100  # Posición del escaneo (fuera de la vista)
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._advance_scan)
        self._scan_timer.setInterval(50)
        self._scan_active = False

        # Texto dinámico
        self._fps = 0.0
        self._eta_text = ""

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def set_progress_info(self, value: int, frag_s: float = 0.0, eta_text: str = "") -> None:
        """Actualiza valor, frag/s y ETA."""
        self.setValue(value)
        self._fps = frag_s
        self._eta_text = eta_text
        self._update_text()

    def start_scan(self) -> None:
        """Inicia la animación de escaneo de luz."""
        self._scan_active = True
        self._scan_timer.start()

    def stop_scan(self) -> None:
        """Detiene la animación de escaneo."""
        self._scan_active = False
        self._scan_timer.stop()
        self._scan_pos = -100
        self.update()

    # ------------------------------------------------------------------ #
    # Lógica interna
    # ------------------------------------------------------------------ #
    def _advance_scan(self) -> None:
        self._scan_pos += 12
        if self._scan_pos > self.width() + 100:
            self._scan_pos = -100
        self.update()

    def _update_text(self) -> None:
        parts = [f"{self.value()}%"]
        if self._fps > 0:
            parts.append(f"{self._fps:.1f} frag/s")
        if self._eta_text:
            parts.append(f"ETA {self._eta_text}")
        self.setFormat("  " + "  |  ".join(parts))

    # ------------------------------------------------------------------ #
    # Pintado
    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        bar_rect = QRectF(1, 1, rect.width() - 2, rect.height() - 2)

        # Dibujar escaneo de luz sobre la barra
        if self._scan_active and self.value() < 100:
            scan_width = 60
            scan_x = self._scan_pos
            grad = QLinearGradient(
                QPointF(scan_x, 0), QPointF(scan_x + scan_width, 0)
            )
            grad.setColorAt(0, QColor(CYAN).darker(150))
            grad.setColorAt(0.5, QColor(CYAN))
            grad.setColorAt(1, QColor(CYAN).darker(150))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawRect(
                QRectF(scan_x, 1, scan_width, rect.height() - 2)
            )

        painter.end()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PULSE CHIP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PulseChip(QFrame):
    """
    Etiqueta con punto que late para indicar estados:
    - EN CURSO (cian, latido rápido)
    - CPU (morado, latido lento)
    - Voces (ámbar, latido lento)
    """

    def __init__(self, label: str = "", color: str = CYAN, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pulseChip")
        self.setFixedHeight(24)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(8)

        # Punto que late
        self._dot = QFrame()
        self._dot.setFixedSize(10, 10)
        self._dot.setObjectName("pulseDot")
        layout.addWidget(self._dot)

        # Texto
        self._label = QLabel(label)
        self._label.setStyleSheet(f"color: {TEXT}; font-size: 11px; font-weight: 700;")
        layout.addWidget(self._label)

        # Color y animación
        self._color = QColor(color)
        self._opacity_effect = QGraphicsOpacityEffect()
        self._dot.setGraphicsEffect(self._opacity_effect)
        self._pulse_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._pulse_anim.setDuration(1200)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._pulse_anim.setLoopCount(-1)  # Infinito

        self._apply_style(color)
        self._start_pulse()

    def _apply_style(self, color: str) -> None:
        self._dot.setStyleSheet(
            f"QFrame#pulseDot {{ background: {color}; border-radius: 5px; }}"
        )
        self.setStyleSheet(
            f"QFrame#pulseChip {{ background: transparent; border: none; }}"
        )

    def _start_pulse(self) -> None:
        self._pulse_anim.setStartValue(0.4)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.start()

    def set_status(self, label: str, color: str = CYAN) -> None:
        """Actualiza texto y color del chip."""
        self._label.setText(label)
        self._color = QColor(color)
        self._dot.setStyleSheet(
            f"QFrame#pulseDot {{ background: {color}; border-radius: 5px; }}"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WAVEFORM WIDGET
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WaveformWidget(QWidget):
    """
    Widget que dibuja una onda de audio animada.
    Se utiliza para mostrar actividad de reproducción o narración en tiempo real.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setMaximumHeight(60)
        self.setMinimumWidth(200)

        self._phase = 0.0
        self._active = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_phase)
        self._timer.setInterval(50)  # 20 FPS

    def start(self) -> None:
        """Inicia la animación de la onda."""
        self._active = True
        self._timer.start()
        self.update()

    def stop(self) -> None:
        """Detiene la animación y deja la onda en reposo."""
        self._active = False
        self._timer.stop()
        self._phase = 0.0
        self.update()

    def _advance_phase(self) -> None:
        self._phase += 0.15
        if self._phase > 2 * math.pi:
            self._phase -= 2 * math.pi
        self.update()

    # ------------------------------------------------------------------ #
    # Pintado
    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        center_y = rect.height() / 2
        amplitude = rect.height() / 3 if self._active else rect.height() / 6

        path = QPainterPath()
        path.moveTo(0, center_y)

        width = rect.width()
        samples = 60
        for i in range(samples + 1):
            x = (i / samples) * width
            # Onda senoidal con desfasado por posición
            y_offset = math.sin((i / samples) * 4 * math.pi + self._phase)
            y = center_y - y_offset * amplitude
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        # Gradiente para la onda
        grad = QLinearGradient(QPointF(0, 0), QPointF(0, rect.height()))
        grad.setColorAt(0, QColor(CYAN))
        grad.setColorAt(1, QColor(MAGENTA))

        painter.setPen(QPen(grad, 2.5))
        painter.drawPath(path)

        # Brillo (glow) detrás de la onda
        glow_pen = QPen(QColor(CYAN))
        glow_pen.setWidth(6)
        glow_pen.setCosmetic(True)
        painter.setPen(glow_pen)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Dibujar una versión más tenue detrás para simular glow
        painter.drawPath(path)

        painter.end()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FRAGMENT CARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FragmentCard(QFrame):
    """
    Tarjeta individual de un fragmento de narración.

    Estados:
    - Normal: borde cian, texto principal.
    - Pausa: borde ámbar, chip "PAUSA".
    - Seleccionada: borde más grueso, fondo ligeramente más claro.
    """

    def __init__(self, number: str, title: str, subtitle: str = "",
                 is_pause: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("fragmentCard")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Número del fragmento
        self._num_label = QLabel(number)
        self._num_label.setFixedSize(30, 26)
        self._num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._num_label.setStyleSheet(
            f"background: #18263D; border-radius: 7px; color: #AEBDD8; "
            f"font-size: 11px; font-weight: 700;"
        )
        layout.addWidget(self._num_label)

        # Contenido de texto
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: 700; background: transparent;"
        )
        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; background: transparent;"
        )
        text_layout.addWidget(self._title_label)
        text_layout.addWidget(self._subtitle_label)
        layout.addLayout(text_layout, 1)

        # Chip de estado (derecha)
        self._chip = QLabel("PAUSA" if is_pause else "")
        self._chip.setFixedHeight(18)
        self._chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chip.setStyleSheet(
            f"background: {'#FFB000' if is_pause else 'transparent'}; "
            f"color: {'#02040A' if is_pause else 'transparent'}; "
            f"border-radius: 9px; font-size: 9px; font-weight: 800; "
            f"padding: 0 8px;"
        )
        self._chip.setVisible(bool(is_pause))
        layout.addWidget(self._chip)

        self._apply_style(is_pause)

    def _apply_style(self, is_pause: bool) -> None:
        border_color = AMBER if is_pause else CYAN
        self.setStyleSheet(
            f"QFrame#fragmentCard {{ "
            f"background: {PANEL_3}; "
            f"border: 2px solid {border_color}; "
            f"border-radius: 10px; "
            f"}}"
            f"QFrame#fragmentCard:hover {{ "
            f"border-color: {CYAN}; "
            f"}}"
        )

    def set_pause(self, is_pause: bool) -> None:
        """Cambia el estado de pausa de la tarjeta."""
        self._chip.setVisible(is_pause)
        self._chip.setText("PAUSA" if is_pause else "")
        self._apply_style(is_pause)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CYBER PANEL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CyberPanel(QFrame):
    """
    Panel con borde y efecto de resplandor (glow) real.
    Útil para contenedores principales que deben resaltar en la UI.
    """

    def __init__(self, glow_color: str = CYAN, blur: int = 18,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("cyberPanel")
        self.setStyleSheet(
            f"QFrame#cyberPanel {{ "
            f"background: {PANEL}; "
            f"border: 1px solid {glow_color}; "
            f"border-radius: 10px; "
            f"}}"
        )
        apply_glow(self, QColor(glow_color), blur=blur)


__all__ = [
    "NeonProgressBar",
    "PulseChip",
    "WaveformWidget",
    "FragmentCard",
    "CyberPanel",
    "apply_glow",
    "PALETTE",
]
