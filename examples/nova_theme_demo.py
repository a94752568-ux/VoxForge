#!/usr/bin/env python3
"""NOVA Theme Demo - Ejemplo de uso del tema NOVA en VoxForge Local.

Este script demuestra cómo aplicar el tema NOVA Premium a una aplicación
PySide6/Qt. Puedes usar este código como base para integrar el tema en tu
interfaz gráfica de VoxForge.

Uso:
    python examples/nova_theme_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QProgressBar,
    QGroupBox,
    QTabWidget,
    QScrollArea,
)
from PySide6.QtCore import Qt

# Importar el tema NOVA
from voxforge.themes import apply_nova_theme, NOVA_CLI_Theme


class VoiceProfileCard(QWidget):
    """Tarjeta de perfil de voz con estilo NOVA."""
    
    def __init__(self, name: str, duration: str, samples: int):
        super().__init__()
        self.setObjectName("voice_card")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Icono (simulado)
        icon_label = QLabel("🎤")
        icon_label.setStyleSheet("font-size: 24px;")
        
        # Información
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #00ffff;")
        
        details_label = QLabel(f"Duración: {duration} | Muestras: {samples}")
        details_label.setStyleSheet("color: #a0a0d0;")
        
        info_layout.addWidget(name_label)
        info_layout.addWidget(details_label)
        
        # Botones
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        btn_play = QPushButton("▶️")
        btn_play.setObjectName("btn_primary")
        btn_play.setFixedSize(32, 32)
        
        btn_edit = QPushButton("✏️")
        btn_edit.setObjectName("btn_accent")
        btn_edit.setFixedSize(32, 32)
        
        btn_delete = QPushButton("🗑️")
        btn_delete.setObjectName("btn_danger")
        btn_delete.setFixedSize(32, 32)
        
        buttons_layout.addWidget(btn_play)
        buttons_layout.addWidget(btn_edit)
        buttons_layout.addWidget(btn_delete)
        
        layout.addWidget(icon_label)
        layout.addLayout(info_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)


class ProjectCard(QWidget):
    """Tarjeta de proyecto con estilo NOVA."""
    
    def __init__(self, title: str, chapters: int, progress: int):
        super().__init__()
        self.setObjectName("project_card")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Título
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #00ffff;")
        
        # Detalles
        details_label = QLabel(f"Capítulos: {chapters} | Progreso: {progress}%")
        details_label.setStyleSheet("color: #a0a0d0;")
        
        # Barra de progreso
        progress_bar = QProgressBar()
        progress_bar.setObjectName("progress_indicator")
        progress_bar.setValue(progress)
        progress_bar.setTextVisible(True)
        progress_bar.setAlignment(Qt.AlignCenter)
        
        # Botones
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        btn_narrate = QPushButton("Narrar")
        btn_narrate.setObjectName("btn_primary")
        
        btn_edit = QPushButton("Editar")
        btn_edit.setObjectName("btn_accent")
        
        btn_export = QPushButton("Exportar")
        btn_export.setObjectName("btn_accent")
        
        buttons_layout.addWidget(btn_narrate)
        buttons_layout.addWidget(btn_edit)
        buttons_layout.addWidget(btn_export)
        
        layout.addWidget(title_label)
        layout.addWidget(details_label)
        layout.addWidget(progress_bar)
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)


class MainWindow(QMainWindow):
    """Ventana principal con tema NOVA."""
    
    def __init__(self):
        super().__init__()
        
        # Configuración de la ventana
        self.setWindowTitle("VoxForge Local - NOVA Theme Demo")
        self.setMinimumSize(1000, 700)
        
        # Widget central
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Cabecera
        header = QWidget()
        header.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #00ffff, stop:1 #0066cc);
            padding: 16px 24px;
        """)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("🎙️ VOXFORGE LOCAL")
        title_label.setStyleSheet("""
            color: white;
            font-size: 24px;
            font-weight: 700;
            letter-spacing: 2px;
        """)
        
        version_label = QLabel("v0.6.0 | NOVA Theme")
        version_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.8);
            font-size: 14px;
        """)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(version_label)
        
        header.setLayout(header_layout)
        main_layout.addWidget(header)
        
        # Contenido principal con pestañas
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                background-color: #12121a;
                border: none;
            }
        """)
        
        # Pestaña: Inicio
        home_tab = QWidget()
        home_layout = QVBoxLayout()
        home_layout.setContentsMargins(24, 24, 24, 24)
        home_layout.setSpacing(20)
        
        # Estadísticas
        stats_group = QGroupBox("📊 Estadísticas")
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        
        stat_card_1 = QWidget()
        stat_card_1.setStyleSheet("""
            background-color: #1a1a25;
            border: 2px solid #0066cc;
            border-radius: 8px;
            padding: 16px;
        """)
        stat_layout_1 = QVBoxLayout()
        stat_label_1 = QLabel("12")
        stat_label_1.setStyleSheet("font-size: 24px; font-weight: 700; color: #00ffff;")
        stat_desc_1 = QLabel("Perfiles de Voz")
        stat_desc_1.setStyleSheet("color: #a0a0d0;")
        stat_layout_1.addWidget(stat_label_1)
        stat_layout_1.addWidget(stat_desc_1)
        stat_card_1.setLayout(stat_layout_1)
        
        stat_card_2 = QWidget()
        stat_card_2.setStyleSheet("""
            background-color: #1a1a25;
            border: 2px solid #0066cc;
            border-radius: 8px;
            padding: 16px;
        """)
        stat_layout_2 = QVBoxLayout()
        stat_label_2 = QLabel("45")
        stat_label_2.setStyleSheet("font-size: 24px; font-weight: 700; color: #00ffff;")
        stat_desc_2 = QLabel("Proyectos")
        stat_desc_2.setStyleSheet("color: #a0a0d0;")
        stat_layout_2.addWidget(stat_label_2)
        stat_layout_2.addWidget(stat_desc_2)
        stat_card_2.setLayout(stat_layout_2)
        
        stat_card_3 = QWidget()
        stat_card_3.setStyleSheet("""
            background-color: #1a1a25;
            border: 2px solid #0066cc;
            border-radius: 8px;
            padding: 16px;
        """)
        stat_layout_3 = QVBoxLayout()
        stat_label_3 = QLabel("1,137")
        stat_label_3.setStyleSheet("font-size: 24px; font-weight: 700; color: #00ffff;")
        stat_desc_3 = QLabel("Fragmentos en Caché")
        stat_desc_3.setStyleSheet("color: #a0a0d0;")
        stat_layout_3.addWidget(stat_label_3)
        stat_layout_3.addWidget(stat_desc_3)
        stat_card_3.setLayout(stat_layout_3)
        
        stats_layout.addWidget(stat_card_1)
        stats_layout.addWidget(stat_card_2)
        stats_layout.addWidget(stat_card_3)
        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        
        # Acciones rápidas
        actions_group = QGroupBox("⚡ Acciones Rápidas")
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        
        btn_new_voice = QPushButton("🎤 Nuevo Perfil de Voz")
        btn_new_voice.setObjectName("btn_primary")
        btn_new_voice.setFixedHeight(48)
        
        btn_new_project = QPushButton("📚 Nuevo Proyecto")
        btn_new_project.setObjectName("btn_primary")
        btn_new_project.setFixedHeight(48)
        
        btn_narrate = QPushButton("🎙️ Narrar Texto")
        btn_narrate.setObjectName("btn_accent")
        btn_narrate.setFixedHeight(48)
        
        actions_layout.addWidget(btn_new_voice)
        actions_layout.addWidget(btn_new_project)
        actions_layout.addWidget(btn_narrate)
        actions_layout.addStretch()
        actions_group.setLayout(actions_layout)
        
        home_layout.addWidget(stats_group)
        home_layout.addWidget(actions_group)
        home_layout.addStretch()
        home_tab.setLayout(home_layout)
        
        # Pestaña: Perfiles de Voz
        voices_tab = QWidget()
        voices_layout = QVBoxLayout()
        voices_layout.setContentsMargins(24, 24, 24, 24)
        voices_layout.setSpacing(12)
        
        voices_scroll = QScrollArea()
        voices_scroll.setWidgetResizable(True)
        voices_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #12121a;
                border: none;
            }
        """)
        
        voices_container = QWidget()
        voices_container_layout = QVBoxLayout()
        voices_container_layout.setSpacing(12)
        voices_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Añadir tarjetas de voz
        voice_profiles = [
            ("María Clara", "2h 34m", 1500),
            ("Carlos Profundo", "3h 12m", 2300),
            ("Ana Natural", "1h 45m", 980),
            ("Jorge Robusto", "4h 20m", 3100),
        ]
        
        for name, duration, samples in voice_profiles:
            card = VoiceProfileCard(name, duration, samples)
            voices_container_layout.addWidget(card)
        
        voices_container.setLayout(voices_container_layout)
        voices_scroll.setWidget(voices_container)
        
        voices_layout.addWidget(voices_scroll)
        voices_tab.setLayout(voices_layout)
        
        # Pestaña: Proyectos
        projects_tab = QWidget()
        projects_layout = QVBoxLayout()
        projects_layout.setContentsMargins(24, 24, 24, 24)
        projects_layout.setSpacing(12)
        
        projects_scroll = QScrollArea()
        projects_scroll.setWidgetResizable(True)
        projects_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #12121a;
                border: none;
            }
        """)
        
        projects_container = QWidget()
        projects_container_layout = QVBoxLayout()
        projects_container_layout.setSpacing(12)
        projects_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Añadir tarjetas de proyecto
        projects = [
            ("El Gran Libro", 12, 85),
            ("Aventuras en Python", 8, 60),
            ("Guía de IA", 15, 30),
            ("Narrativa Digital", 6, 100),
        ]
        
        for title, chapters, progress in projects:
            card = ProjectCard(title, chapters, progress)
            projects_container_layout.addWidget(card)
        
        projects_container.setLayout(projects_container_layout)
        projects_scroll.setWidget(projects_container)
        
        projects_layout.addWidget(projects_scroll)
        projects_tab.setLayout(projects_layout)
        
        # Pestaña: Configuración
        settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(24, 24, 24, 24)
        settings_layout.setSpacing(20)
        
        # Configuración de voz
        voice_settings_group = QGroupBox("🎤 Configuración de Voz")
        voice_settings_layout = QVBoxLayout()
        voice_settings_layout.setSpacing(12)
        
        # Selector de perfil
        profile_layout = QHBoxLayout()
        profile_label = QLabel("Perfil por defecto:")
        profile_combo = QComboBox()
        profile_combo.addItems(["María Clara", "Carlos Profundo", "Ana Natural"])
        profile_layout.addWidget(profile_label)
        profile_layout.addWidget(profile_combo)
        profile_layout.addStretch()
        
        # Configuración de calidad
        quality_layout = QHBoxLayout()
        quality_label = QLabel("Calidad de síntesis:")
        quality_combo = QComboBox()
        quality_combo.addItems(["Estándar", "Alta", "Máxima"])
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(quality_combo)
        quality_layout.addStretch()
        
        # Configuración de pausas
        pause_layout = QHBoxLayout()
        pause_label = QLabel("Pausa entre fragmentos (ms):")
        pause_spin = QSpinBox()
        pause_spin.setRange(0, 5000)
        pause_spin.setValue(350)
        pause_layout.addWidget(pause_label)
        pause_layout.addWidget(pause_spin)
        pause_layout.addStretch()
        
        voice_settings_layout.addLayout(profile_layout)
        voice_settings_layout.addLayout(quality_layout)
        voice_settings_layout.addLayout(pause_layout)
        voice_settings_group.setLayout(voice_settings_layout)
        
        # Configuración de caché
        cache_settings_group = QGroupBox("💾 Configuración de Caché")
        cache_settings_layout = QVBoxLayout()
        cache_settings_layout.setSpacing(12)
        
        cache_enabled_layout = QHBoxLayout()
        cache_enabled_check = QCheckBox("Habilitar caché")
        cache_enabled_check.setChecked(True)
        cache_enabled_layout.addWidget(cache_enabled_check)
        cache_enabled_layout.addStretch()
        
        cache_size_layout = QHBoxLayout()
        cache_size_label = QLabel("Tamaño máximo (GB):")
        cache_size_spin = QSpinBox()
        cache_size_spin.setRange(1, 100)
        cache_size_spin.setValue(10)
        cache_size_layout.addWidget(cache_size_label)
        cache_size_layout.addWidget(cache_size_spin)
        cache_size_layout.addStretch()
        
        cache_settings_layout.addLayout(cache_enabled_layout)
        cache_settings_layout.addLayout(cache_size_layout)
        cache_settings_group.setLayout(cache_settings_layout)
        
        # Botón de guardar
        save_btn = QPushButton("💾 Guardar Configuración")
        save_btn.setObjectName("btn_primary")
        save_btn.setFixedHeight(40)
        
        settings_layout.addWidget(voice_settings_group)
        settings_layout.addWidget(cache_settings_group)
        settings_layout.addStretch()
        settings_layout.addWidget(save_btn)
        settings_tab.setLayout(settings_layout)
        
        # Añadir pestañas
        tab_widget.addTab(home_tab, "🏠 Inicio")
        tab_widget.addTab(voices_tab, "🎤 Voces")
        tab_widget.addTab(projects_tab, "📚 Proyectos")
        tab_widget.addTab(settings_tab, "⚙️ Configuración")
        
        main_layout.addWidget(tab_widget)
        
        # Barra de estado
        status_bar = QWidget()
        status_bar.setStyleSheet("""
            background-color: #0a0a0f;
            border-top: 2px solid #2a2a40;
            padding: 8px 24px;
        """)
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        status_label = QLabel("Listo | CPU: 71°C | Caché: 327.34 MB")
        status_label.setStyleSheet("color: #a0a0d0;")
        
        status_layout.addWidget(status_label)
        status_layout.addStretch()
        
        status_bar.setLayout(status_layout)
        main_layout.addWidget(status_bar)
        
        # Conectar señales (opcional, para demo)
        self._connect_signals()
        
        # Mostrar mensaje en terminal
        print(NOVA_CLI_Theme.title("\nNOVA Theme Demo - VoxForge Local"))
        print(NOVA_CLI_Theme.header("=" * 50))
        print(NOVA_CLI_Theme.success("✓ Theme NOVA aplicado correctamente!"))
        print(NOVA_CLI_Theme.info("ℹ Demo de interfaz gráfica con estilo cyberpunk"))
        print(NOVA_CLI_Theme.muted("\nPresiona CTRL+C para cerrar...\n"))

    def _connect_signals(self):
        """Conectar señales para interactividad."""
        # Puedes añadir aquí conexiones de botones para la demo
        pass


def main():
    """Función principal."""
    app = QApplication(sys.argv)
    
    # Aplicar el tema NOVA
    apply_nova_theme(app)
    
    # Crear y mostrar la ventana principal
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n" + NOVA_CLI_Theme.warning("Demo cerrada por el usuario"))
        sys.exit(0)
