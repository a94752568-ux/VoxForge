"""
main_window.py — Ventana principal estilo Night City para VoxForge.

Layout de 3 columnas:
  Columna 1: Proyectos / Capítulos / Flujo de trabajo
  Columna 2: Proyecto activo + Fragmentos
  Columna 3: Trabajos / Registro
  Abajo: Reproductor de audio

Solo PySide6 + stdlib. 100% offline. Sin dependencias de red.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .theme import PALETTE, QSS
from .widgets import (
    CyberPanel,
    FragmentCard,
    NeonProgressBar,
    PulseChip,
    WaveformWidget,
    apply_glow,
)

CYAN = PALETTE["cyan"]
MAGENTA = PALETTE["magenta"]
PURPLE = PALETTE["purple"]
AMBER = PALETTE["amber"]
GREEN = PALETTE["green"]
TEXT = PALETTE["text"]
MUTED = PALETTE["muted"]
BG = PALETTE["bg"]
PANEL = PALETTE["panel"]
PANEL_2 = PALETTE["panel2"]
PANEL_3 = PALETTE["panel3"]
BORDER = "#1E2438"


class MainWindow(QMainWindow):
    """
    Ventana principal de VoxForge con estilo Night City.

    Estructura:
      - Barra de título personalizada (frameless look)
      - 3 columnas principales vía QSplitter
      - Reproductor de audio en la parte inferior
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VoxForge · Estudio de narración local")
        self.resize(1000, 700)
        self.setMinimumSize(700, 500)

        self._build_ui()
        self._apply_theme()
        self._start_demo_animations()

    # ------------------------------------------------------------------ #
    # Construcción de la UI
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Barra de título personalizada ---
        title_bar = self._build_title_bar()
        root.addWidget(title_bar)

        # --- Contenido principal (3 columnas) ---
        content = QWidget()
        content.setObjectName("mainContent")
        root.addWidget(content, 1)

        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        content_layout.addWidget(splitter)

        # Columna 1: Proyectos / Capítulos / Flujo
        col1 = self._build_column_1()
        splitter.addWidget(col1)

        # Columna 2: Proyecto activo + Fragmentos
        col2 = self._build_column_2()
        splitter.addWidget(col2)

        # Columna 3: Trabajos / Registro
        col3 = self._build_column_3()
        splitter.addWidget(col3)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)

        # --- Reproductor de audio (abajo) ---
        player_bar = self._build_player_bar()
        root.addWidget(player_bar)

    # ------------------------------------------------------------------ #
    # Barra de título
    # ------------------------------------------------------------------ #
    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            f"QWidget#titleBar {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {PALETTE['dark']}, stop:1 {PALETTE['panel']}); "
            f"border-bottom: 1px solid BORDER; "
            f"}}"
        )

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Logo + título
        logo = QLabel("V")
        logo.setFixedSize(34, 34)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {CYAN}, stop:1 {PURPLE}); "
            f"color: PALETTE['dark']; border-radius: 10px; font-size: 18px; font-weight: 900;"
        )
        layout.addWidget(logo)

        title = QLabel("VOXFORGE")
        title.setObjectName("title")
        title.setStyleSheet(
            f"color: {CYAN}; font-size: 17px; font-weight: 800; letter-spacing: 2px;"
        )
        layout.addWidget(title)

        sub = QLabel("NARRACIÓN LOCAL")
        sub.setStyleSheet(f"color: {MUTED}; font-size: 10px; font-weight: 700;")
        layout.addWidget(sub)

        layout.addStretch(1)

        # Estado del sistema (chip)
        self.system_chip = PulseChip("SISTEMA · LISTO", CYAN)
        layout.addWidget(self.system_chip)

        # Botones de ventana
        btn_close = QPushButton("✕")
        btn_close.setObjectName("btnClose")
        btn_close.setFixedSize(32, 32)
        btn_close.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED}; "
            f"border-radius: 6px; font-size: 16px; }}"
            f"QPushButton:hover {{ background: {MAGENTA}22; color: {MAGENTA}; }}"
        )
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

        return bar

    # ------------------------------------------------------------------ #
    # Columna 1: Proyectos / Capítulos / Flujo
    # ------------------------------------------------------------------ #
    def _build_column_1(self) -> QWidget:
        panel = CyberPanel(glow_color=CYAN, blur=14)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)

        # Sección Proyectos
        section1 = QLabel("PROYECTOS")
        section1.setObjectName("section")
        section1.setStyleSheet(f"color: {CYAN}; font-size: 9px; font-weight: 800; letter-spacing: 1px;")
        lay.addWidget(section1)

        self.projects_list = QListWidget()
        self.projects_list.setObjectName("projectsList")
        self.projects_list.addItem("Vasconcelos_Jos__La_Raza_C.smica_19")
        self.projects_list.addItem("Capítulo 01 · Parte 01")
        self.projects_list.setMinimumHeight(120)
        lay.addWidget(self.projects_list)

        btn_import = QPushButton("＋  Importar libro")
        btn_import.setObjectName("primary")
        btn_import.setMinimumHeight(36)
        lay.addWidget(btn_import)

        lay.addSpacing(8)

        # Sección Capítulos
        section2 = QLabel("CAPÍTULOS")
        section2.setObjectName("section")
        section2.setStyleSheet(f"color: {CYAN}; font-size: 9px; font-weight: 800; letter-spacing: 1px;")
        lay.addWidget(section2)

        self.chapters_list = QListWidget()
        self.chapters_list.setObjectName("chaptersList")
        self.chapters_list.addItem("01 · Parte 01 — 14.075 car. · ~73 min")
        self.chapters_list.addItem("02 · Parte 02 — 43.157 car. · ~72 min")
        self.chapters_list.setMinimumHeight(100)
        lay.addWidget(self.chapters_list)

        lay.addStretch(1)

        # Flujo de trabajo
        guide = QFrame()
        guide.setObjectName("sideCard")
        guide.setStyleSheet(
            f"QFrame#sideCard {{ "
            f"background: {PANEL_3}; "
            f"border: 1px solid BORDER; "
            f"border-radius: 10px; "
            f"}}"
        )
        guide_lay = QVBoxLayout(guide)
        guide_lay.setContentsMargins(12, 10, 12, 10)
        guide_lay.setSpacing(6)

        guide_title = QLabel("FLUJO DE TRABAJO")
        guide_title.setObjectName("section")
        guide_title.setStyleSheet(f"color: {CYAN}; font-size: 9px; font-weight: 800;")
        guide_lay.addWidget(guide_title)

        for step in ("1 · Importa un libro", "2 · Elige un capítulo", "3 · Narra o regenera"):
            lbl = QLabel(step)
            lbl.setObjectName("sideStep")
            lbl.setStyleSheet(
                f"color: {MUTED}; font-size: 11px; padding: 4px 0;"
            )
            guide_lay.addWidget(lbl)

        lay.addWidget(guide)

        return panel

    # ------------------------------------------------------------------ #
    # Columna 2: Proyecto activo + Fragmentos
    # ------------------------------------------------------------------ #
    def _build_column_2(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Cabecera contextual
        ctx = QFrame()
        ctx.setObjectName("contextHeader")
        ctx.setStyleSheet(
            f"QFrame#contextHeader {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 #122138, stop:1 #0B1424); "
            f"border-bottom: 1px solid BORDER; "
            f"}}"
        )
        ctx_lay = QHBoxLayout(ctx)
        ctx_lay.setContentsMargins(18, 12, 18, 12)
        ctx_lay.setSpacing(12)

        eyebrow = QLabel("BIBLIOTECA")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setStyleSheet(f"color: {CYAN}; font-size: 9px; font-weight: 800; letter-spacing: 1px;")
        ctx_lay.addWidget(eyebrow)

        self.ctx_title = QLabel("Vasconcelos_Jos__La_Raza_C.smica_19")
        self.ctx_title.setObjectName("title")
        self.ctx_title.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: 800;")
        ctx_lay.addWidget(self.ctx_title)

        self.ctx_sub = QLabel("Capítulo 01 · Parte 01 · 215 fragmentos")
        self.ctx_sub.setObjectName("subtitle")
        self.ctx_sub.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        ctx_lay.addWidget(self.ctx_sub)

        ctx_lay.addStretch(1)

        # Badges
        for text, color in (("7 voces", CYAN), ("1280 en caché", PURPLE), ("CPU 65°C", AMBER)):
            chip = PulseChip(text, color)
            ctx_lay.addWidget(chip)

        lay.addWidget(ctx)

        # Tarjeta de fragmentos
        frag_card = QFrame()
        frag_card.setObjectName("fragmentsCard")
        frag_card.setStyleSheet(
            f"QFrame#fragmentsCard {{ "
            f"background: {PANEL}; "
            f"border: 1px solid BORDER; "
            f"border-radius: 10px; "
            f"}}"
        )
        frag_lay = QVBoxLayout(frag_card)
        frag_lay.setContentsMargins(16, 12, 16, 12)
        frag_lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        f_title = QLabel("FRAGMENTOS")
        f_title.setObjectName("cardTitle")
        f_title.setStyleSheet(f"color: {PURPLE}; font-size: 11px; font-weight: 800; letter-spacing: 1px;")
        head.addWidget(f_title)

        self.lbl_frag_count = QLabel("215 fragmentos · 5 pausas")
        self.lbl_frag_count.setObjectName("count")
        self.lbl_frag_count.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        head.addWidget(self.lbl_frag_count)
        head.addStretch(1)

        frag_lay.addLayout(head)

        # Lista de fragmentos (ejemplo visual)
        self.fragments_list = QListWidget()
        self.fragments_list.setObjectName("fragmentsList")
        self.fragments_list.setSpacing(4)
        self.fragments_list.setAlternatingRowColors(True)

        demo_fragments = [
            ("01", "Pause explícita", "1.5 s de silencio", False),
            ("02", "LA RAZA CÓSMICA", "15 caracteres", False),
            ("03", "Edición original: Madrid, Agencia Mundial de Librería, 1925.", "151 caracteres", False),
            ("04", "Pause explícita", "1.5 s de silencio", True),  # pausa
        ]

        for num, title, sub, is_pause in demo_fragments:
            card = FragmentCard(num, title, sub, is_pause=is_pause)
            item = QListWidgetItem()
            item.setSizeHint(card.sizeHint())
            self.fragments_list.addItem(item)
            self.fragments_list.setItemWidget(item, card)

        frag_lay.addWidget(self.fragments_list, 1)
        lay.addWidget(frag_card, 1)

        return panel

    # ------------------------------------------------------------------ #
    # Columna 3: Trabajos / Registro
    # ------------------------------------------------------------------ #
    def _build_column_3(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Pestañas Trabajos / Exportaciones
        from PySide6.QtWidgets import QTabWidget

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setStyleSheet(
            f"QTabWidget::pane {{ "
            f"border: 1px solid BORDER; "
            f"border-radius: 10px; "
            f"background: {PANEL}; "
            f"}}"
            f"QTabBar::tab {{ "
            f"background: {PANEL_3}; "
            f"color: {MUTED}; "
            f"padding: 8px 18px; "
            f"margin-right: 4px; "
            f"border-top-left-radius: 10px; "
            f"border-top-right-radius: 10px; "
            f"}}"
            f"QTabBar::tab:selected {{ "
            f"background: {PANEL}; "
            f"color: {CYAN}; "
            f"border: 1px solid {CYAN}; "
            f"border-bottom: 2px solid {CYAN}; "
            f"}}"
        )

        # Pestaña Trabajos
        jobs_page = QWidget()
        jobs_lay = QVBoxLayout(jobs_page)
        jobs_lay.setContentsMargins(12, 12, 12, 12)
        jobs_lay.setSpacing(10)

        j_head = QHBoxLayout()
        j_title = QLabel("TRABAJOS")
        j_title.setObjectName("cardTitle")
        j_title.setStyleSheet(f"color: {PURPLE}; font-size: 11px; font-weight: 800;")
        j_head.addWidget(j_title)
        j_head.addStretch(1)
        jobs_lay.addLayout(j_head)

        self.jobs_list = QListWidget()
        self.jobs_list.setObjectName("jobsList")
        self.jobs_list.setSpacing(4)
        self.jobs_list.setAlternatingRowColors(True)

        # Trabajo de demostración
        job_card = QFrame()
        job_card.setObjectName("jobCard")
        job_card.setStyleSheet(
            f"QFrame#jobCard {{ "
            f"background: {PANEL_3}; "
            f"border: 1px solid BORDER; "
            f"border-radius: 10px; "
            f"}}"
        )
        job_lay = QVBoxLayout(job_card)
        job_lay.setContentsMargins(12, 10, 12, 10)
        job_lay.setSpacing(6)

        j_top = QHBoxLayout()
        j_proj = QLabel("import_Ruso_cap_1")
        j_proj.setStyleSheet(f"color: {TEXT}; font-weight: 700; font-size: 12px;")
        j_top.addWidget(j_proj)
        j_top.addStretch(1)
        j_status = QLabel("En curso")
        j_status.setObjectName("chipAccent")
        j_status.setStyleSheet(f"color: {CYAN}; font-size: 10px; font-weight: 700; background: rgba(0,240,255,0.1); border: 1px solid {CYAN}; border-radius: 8px; padding: 2px 8px;")
        j_top.addWidget(j_status)
        job_lay.addLayout(j_top)

        j_bar = NeonProgressBar()
        j_bar.set_progress_info(45, frag_s=2.3, eta_text="2m 15s")
        j_bar.start_scan()
        job_lay.addWidget(j_bar)

        j_meta = QLabel("00:04:23 transcurridos · quedan ≈ 00:02:15")
        j_meta.setObjectName("progMeta")
        j_meta.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        job_lay.addWidget(j_meta)

        jobs_lay.addWidget(job_card)

        # Registro
        reg_title = QLabel("REGISTRO")
        reg_title.setObjectName("section")
        reg_title.setStyleSheet(f"color: {CYAN}; font-size: 9px; font-weight: 800;")
        jobs_lay.addWidget(reg_title)

        self.log_view = QListWidget()
        self.log_view.setObjectName("logView")
        self.log_view.setStyleSheet(
            f"QListWidget#logView {{ "
            f"background: PALETTE['panel']; "
            f"border: 1px solid BORDER; "
            f"border-radius: 8px; "
            f"color: PALETTE['text']; "
            f"font-family: monospace; "
            f"font-size: 10px; "
            f"}}"
        )
        self.log_view.addItem("[voxforge-job] runner pid=46426 job=3")
        self.log_view.addItem("[Copia] 0/234 transcritos · estimación pendiente")
        jobs_lay.addWidget(self.log_view, 1)

        self.tabs.addTab(jobs_page, "Trabajos")

        # Pestaña Exportaciones (vacía por ahora)
        exp_page = QWidget()
        exp_lay = QVBoxLayout(exp_page)
        exp_lay.setContentsMargins(12, 12, 12, 12)
        exp_lay.setSpacing(10)

        e_title = QLabel("EXPORTACIONES")
        e_title.setObjectName("cardTitle")
        e_title.setStyleSheet(f"color: {PURPLE}; font-size: 11px; font-weight: 800;")
        exp_lay.addWidget(e_title)

        exp_empty = QLabel("Sin exportaciones todavía.\nGenera un piloto o un máster para verlo aquí.")
        exp_empty.setObjectName("subtitle")
        exp_empty.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        exp_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        exp_lay.addWidget(exp_empty)
        exp_lay.addStretch(1)

        self.tabs.addTab(exp_page, "Exportaciones")

        lay.addWidget(self.tabs, 1)

        return panel

    # ------------------------------------------------------------------ #
    # Reproductor de audio (abajo)
    # ------------------------------------------------------------------ #
    def _build_player_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("playerBar")
        bar.setMinimumHeight(80)
        bar.setMaximumHeight(80)
        bar.setStyleSheet(
            f"QFrame#playerBar {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {PANEL_2}, stop:1 {PANEL}); "
            f"border-top: 1px solid BORDER; "
            f"}}"
        )

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(16)

        # Arte / icono
        art = QLabel("V")
        art.setObjectName("playerArt")
        art.setFixedSize(44, 44)
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        art.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {CYAN}, stop:1 {PURPLE}); "
            f"color: PALETTE['dark']; border-radius: 10px; font-size: 20px; font-weight: 900;"
        )
        lay.addWidget(art)

        # Información
        info = QVBoxLayout()
        info.setSpacing(2)
        self.player_file = QLabel("001_preview30.wav")
        self.player_file.setObjectName("playerFile")
        self.player_file.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700;")
        info.addWidget(self.player_file)

        self.player_sub = QLabel("Sin reproducción · Doble clic en una exportación")
        self.player_sub.setObjectName("playerSub")
        self.player_sub.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        info.addWidget(self.player_sub)
        lay.addLayout(info, 1)

        # Controles
        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("play")
        self.btn_play.setFixedSize(40, 40)
        self.btn_play.setStyleSheet(
            f"QPushButton#play {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {CYAN}, stop:1 {PURPLE}); "
            f"color: PALETTE['dark']; border: none; border-radius: 20px; "
            f"font-size: 15px; font-weight: 900; "
            f"}}"
            f"QPushButton#play:hover {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 #8FF7E6, stop:1 #BC13FE); "
            f"}}"
        )
        lay.addWidget(self.btn_play)

        self.btn_stop = QPushButton("■")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setFixedSize(34, 34)
        self.btn_stop.setStyleSheet(
            f"QPushButton#btnStop {{ "
            f"background: {PANEL_3}; "
            f"color: {MUTED}; border: 1px solid BORDER; "
            f"border-radius: 8px; "
            f"}}"
            f"QPushButton#btnStop:hover {{ "
            f"background: PALETTE['panel3']; "
            f"}}"
        )
        lay.addWidget(self.btn_stop)

        # Barra de progreso del reproductor
        self.player_progress = NeonProgressBar()
        self.player_progress.set_progress_info(0, 0.0, "--:--")
        lay.addWidget(self.player_progress, 1)

        # Tiempo
        self.player_time = QLabel("0:00 / 0:00")
        self.player_time.setObjectName("time")
        self.player_time.setStyleSheet(f"color: {PURPLE}; font-size: 10px; font-family: monospace;")
        lay.addWidget(self.player_time)

        # Volumen
        vol_label = QLabel("VOL")
        vol_label.setObjectName("count")
        vol_label.setStyleSheet(f"color: {MUTED}; font-size: 10px; font-weight: 700;")
        lay.addWidget(vol_label)

        from PySide6.QtWidgets import QSlider
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(100)
        self.vol_slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ height: 4px; background: #1A2842; border-radius: 2px; }}"
            f"QSlider::sub-page:horizontal {{ background: {CYAN}; border-radius: 2px; }}"
            f"QSlider::handle:horizontal {{ width: 14px; margin: -5px 0; border-radius: 7px; "
            f"background: PALETTE['text']; border: 1px solid {CYAN}; }}"
        )
        lay.addWidget(self.vol_slider)

        self.vol_value = QLabel("80 %")
        self.vol_value.setObjectName("time")
        self.vol_value.setStyleSheet(f"color: {PURPLE}; font-size: 10px; font-family: monospace;")
        lay.addWidget(self.vol_value)

        return bar

    # ------------------------------------------------------------------ #
    # Aplicar tema
    # ------------------------------------------------------------------ #
    def _apply_theme(self) -> None:
        self.setStyleSheet(QSS)

    # ------------------------------------------------------------------ #
    # Animaciones demo (se desconectan al conectar lógica real)
    # ------------------------------------------------------------------ #
    def _start_demo_animations(self) -> None:
        """Inicia animaciones de demostración. Se reemplazan por lógica real."""
        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._tick_demo)
        self._demo_timer.setInterval(800)
        self._demo_timer.start()

        self._demo_value = 0
        self._demo_direction = 1

    def _tick_demo(self) -> None:
        """Simula progreso de un trabajo para demostración visual."""
        self._demo_value += self._demo_direction * 5
        if self._demo_value >= 100:
            self._demo_value = 100
            self._demo_direction = -1
        elif self._demo_value <= 0:
            self._demo_value = 0
            self._demo_direction = 1

        # Actualizar barra de progreso del trabajo en la columna 3
        if hasattr(self, "jobs_list") and self.jobs_list.count() > 0:
            # Actualizar barra de progreso si existe
            pass

        # Actualizar reproductor
        self.player_progress.set_progress_info(
            self._demo_value,
            frag_s=2.3,
            eta_text=f"00:{max(0, 20 - self._demo_value // 5):02d}" if self._demo_value < 100 else "Completado"
        )
        if self._demo_value < 100:
            self.player_progress.start_scan()
        else:
            self.player_progress.stop_scan()

        # Actualizar onda
        if not hasattr(self, "_waveform"):
            # Crear onda en el reproductor si no existe
            pass


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Aplicar QSS cyberpunk
    from .theme import QSS
    app.setStyleSheet(QSS)

    # Fuente
    from PySide6.QtGui import QFontDatabase, QFont
    families = set(QFontDatabase.families())
    for family in ("Segoe UI", "Inter", "Lato", "Noto Sans", "DejaVu Sans", "Sans Serif"):
        if family in families:
            app.setFont(QFont(family, 10))
            break

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
