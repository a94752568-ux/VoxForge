#!/usr/bin/env python3
"""Panel de producción PySide6 para VoxForge Local.

Fase 5.3 «Aurora»: barra lateral de biblioteca, cabecera contextual, tarjetas
con estados vacíos, pestañas de trabajos/exportaciones y reproductor con
búsqueda y control de posición.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import soundfile as sf

try:
    from PySide6.QtCore import (
        QIdentityProxyModel,
        QEasingCurve,
        QLibraryInfo,
        QPoint,
        QProcess,
        QProcessEnvironment,
        QPropertyAnimation,
        QRect,
        QRectF,
        QSize,
        Qt,
        QTimer,
        QThread,
        QTranslator,
        QUrl,
        Signal,
    )
    from PySide6.QtGui import (
        QColor,
        QDesktopServices,
        QFont,
        QFontDatabase,
        QFontMetrics,
        QIcon,
        QKeySequence,
        QLinearGradient,
        QPainter,
        QPen,
        QPixmap,
        QShortcut,
        QTextCursor,
    )
    from PySide6.QtWidgets import (
        QAbstractButton,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSizePolicy,
        QSlider,
        QSplitter,
        QStackedWidget,
        QStyle,
        QStyledItemDelegate,
        QTabWidget,
        QTextEdit,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
    try:
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        HAS_MULTIMEDIA = True
    except ImportError:
        HAS_MULTIMEDIA = False
except ImportError as exc:
    raise SystemExit(
        "Falta PySide6. Instala con:\n"
        "  uv pip install --python \"$PWD/.venv/bin/python\" PySide6\n"
        f"Error original: {exc}"
    )

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voxforge.audioqa import analyze, verdict
from voxforge.config import home, load_settings
from voxforge.db import Store
from voxforge.jobs import JobStore
from voxforge.pausetext import PauseError
from voxforge.projects import (
    ChapterNotFound,
    ProjectError,
    ProjectNotFound,
    delete_project,
    get_chapter,
    get_project,
    list_chapters,
    list_projects,
    update_chapter,
)
from voxforge.services import (
    ProjectService,
    VoiceManagerService,
    ProjectRequest,
    ChapterRequest,
)
from voxforge.services.narrator import NarratorService, NarrationRequest
from voxforge.pronunciation import PronunciationError, load_pronunciation
from voxforge.textutil import split_segments
from voxforge.voicefx import PRESETS
from voxforge.thermal import cpu_temp_c

# --------------------------------------------------------------------------- #
# Constantes de coste / estilo                                                 #
# --------------------------------------------------------------------------- #

ENABLE_ANIM = True
REFRESH_RUNNING_MS = 1000
REFRESH_IDLE_MS = 2500
FX_MS = 60

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".oga", ".m4a", ".aac"}
IMPORT_EXTS = {".txt", ".md", ".docx", ".epub", ".pdf"}
IMPORT_FILTER = "Libros (*.txt *.md *.docx *.epub *.pdf);;Todos los archivos (*)"
VOICE_EXTS = {".wav", ".flac", ".mp3", ".ogg", ".oga", ".m4a", ".aac", ".opus"}
VOICE_FILTER = "Audio (*.wav *.flac *.mp3 *.ogg *.oga *.m4a *.aac *.opus);;Todos los archivos (*)"

from voxforge.ui.theme import QSS, CYAN, PURPLE, MUTED, MAGENTA, DEFAULT_THEME



# --------------------------------------------------------------------------- #
# Roles y tarjetas de lista                                                    #
# --------------------------------------------------------------------------- #

ROLE_ID = int(Qt.UserRole)
ROLE_TITLE = ROLE_ID + 1
ROLE_SUB = ROLE_ID + 2
ROLE_BADGE = ROLE_ID + 3
ROLE_BADGE_COLOR = ROLE_ID + 4
ROLE_NUMBER = ROLE_ID + 5
ROLE_ACCENT = ROLE_ID + 6


class EmptyList(QListWidget):
    """Lista con un mensaje de estado vacío dibujado dentro."""

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.placeholder = placeholder
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def setPlaceholder(self, text: str) -> None:
        self.placeholder = text
        self.viewport().update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if self.count() == 0 and self.placeholder:
            from PySide6.QtGui import QPainter, QColor
            from PySide6.QtCore import Qt as _Qt

            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QColor(MUTED))
            font = self.font()
            font.setPixelSize(11)
            painter.setFont(font)
            rect = self.viewport().rect()
            painter.drawText(
                rect,
                _Qt.AlignmentFlag.AlignCenter | _Qt.AlignmentFlag.AlignVCenter,
                self.placeholder,
            )
            painter.end()


class CardDelegate(QStyledItemDelegate):
    """Dibuja cada fila como una tarjeta con título, subtítulo y chip de estado."""

    def __init__(self, *, height: int = 58, parent=None):
        super().__init__(parent)
        self.height = height
        # Cache de objetos de dibujo reusables (evita asignaciones por frame)
        self._title_font = QFont()
        self._title_font.setPixelSize(13)
        self._title_font.setWeight(QFont.Weight.DemiBold)
        self._sub_font = QFont()
        self._sub_font.setPixelSize(11)
        self._badge_font = QFont()
        self._badge_font.setPixelSize(9)
        self._badge_font.setWeight(QFont.Weight.DemiBold)
        self._num_font = QFont()
        self._num_font.setPixelSize(11)
        self._num_font.setWeight(QFont.Weight.DemiBold)
        self._pen_no = QPen(Qt.PenStyle.NoPen)
        self._pen_selected = QPen(QColor("#f2f7ff"))
        self._pen_normal = QPen(QColor("#dbe6f7"))
        self._pen_sub_selected = QPen(QColor("#9fb0cc"))
        self._pen_sub_normal = QPen(QColor(MUTED))
        self._pen_number = QPen(QColor("#aebdd8"))
        self._brush_num_bg = QBrush(QColor("#18263d"))

    def sizeHint(self, option, index):
        return QSize(0, self.height)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = option.rect.adjusted(2, 2, -2, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if selected:
            bg, border = QColor("#15243d"), QColor("#31507a")
        elif hover:
            bg, border = QColor("#121e33"), QColor("#243654")
        else:
            bg, border = QColor("#0e1728"), QColor("#1a2942")

        painter.setPen(QPen(border, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 10, 10)

        accent_value = index.data(ROLE_ACCENT)
        if selected or accent_value:
            accent = QColor(accent_value or CYAN)
            if not selected:
                accent.setAlpha(165)
            painter.setPen(self._pen_no)
            painter.setBrush(accent)
            painter.drawRoundedRect(
                QRectF(rect.left() + 1, rect.top() + 10, 3, rect.height() - 20), 1.5, 1.5
            )

        x = rect.left() + 12
        number = index.data(ROLE_NUMBER)
        if number is not None and str(number) != "":
            box = QRect(x, rect.center().y() - 13, 30, 26)
            painter.setPen(self._pen_no)
            painter.setBrush(self._brush_num_bg)
            painter.drawRoundedRect(box, 7, 7)
            painter.setPen(self._pen_number)
            painter.setFont(self._num_font)
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, str(number))
            x += 40

        badge = index.data(ROLE_BADGE)
        badge_w = 0
        if badge:
            color = QColor(index.data(ROLE_BADGE_COLOR) or MUTED)
            painter.setFont(self._badge_font)
            badge_w = QFontMetrics(self._badge_font).horizontalAdvance(str(badge)) + 16
            badge_rect = QRect(
                rect.right() - 12 - badge_w, rect.center().y() - 9, badge_w, 18
            )
            tint = QColor(color)
            tint.setAlpha(28)
            painter.setPen(QPen(color, 1))
            painter.setBrush(tint)
            painter.drawRoundedRect(badge_rect, 9, 9)
            painter.setPen(color)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, str(badge))

        text_right = rect.right() - 14 - (badge_w + 8 if badge_w else 0)
        width = max(40, text_right - x)

        title = str(index.data(ROLE_TITLE) or index.data(Qt.ItemDataRole.DisplayRole) or "")
        subtitle = str(index.data(ROLE_SUB) or "")

        painter.setFont(self._title_font)
        painter.setPen(self._pen_selected if selected else self._pen_normal)
        fm_title = QFontMetrics(self._title_font)
        title = fm_title.elidedText(title, Qt.TextElideMode.ElideRight, width)
        if subtitle:
            painter.drawText(
                QRect(x, rect.top() + 9, width, 18),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                title,
            )
            painter.setFont(self._sub_font)
            painter.setPen(self._pen_sub_selected if selected else self._pen_sub_normal)
            fm_sub = QFontMetrics(self._sub_font)
            subtitle = fm_sub.elidedText(subtitle, Qt.TextElideMode.ElideRight, width)
            painter.drawText(
                QRect(x, rect.top() + 29, width, 16),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                subtitle,
            )
        else:
            painter.drawText(
                rect.adjusted(x - rect.left(), 0, -14, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                title,
            )

        painter.restore()



    """Lista con un mensaje de estado vacío dibujado dentro."""

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.placeholder = placeholder
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.count() or not self.placeholder:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QColor("#6b7c99"))
        font = QFont(self.font())
        font.setPixelSize(11)
        font.setItalic(True)
        painter.setFont(font)
        painter.drawText(
            self.viewport().rect().adjusted(22, 30, -22, -22),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap,
            self.placeholder,
        )
        painter.end()




class SpanishFileHeaders(QIdentityProxyModel):
    """Traduce las cabeceras del explorador de archivos de Qt."""

    _HEADERS = ("Nombre", "Tamaño", "Tipo", "Modificado")

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self._HEADERS)
        ):
            return self._HEADERS[section]
        return super().headerData(section, orientation, role)


class AudioAnalyzeThread(QThread):
    """Lee y analiza una muestra de voz en un hilo de fondo para no bloquear la UI."""

    finished = Signal(object)

    def __init__(self, path: str | Path, parent=None):
        super().__init__(parent)
        self.path = str(path)

    def run(self) -> None:  # type: ignore[override]
        import soundfile as sf
        from voxforge.audioqa import analyze

        try:
            audio, sr = sf.read(self.path, dtype="float32")
            self.finished.emit(analyze(audio, sr))
        except Exception:
            self.finished.emit([])


def pick_file(parent, caption: str, start: str, filter_text: str) -> str | None:
    """Explorador de archivos oscuro, en español y con cabeceras traducidas."""
    dialog = QFileDialog(parent, caption, start, filter_text)
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    dialog.setProxyModel(SpanishFileHeaders(dialog))
    dialog.setLabelText(QFileDialog.DialogLabel.LookIn, "Buscar en:")
    dialog.setLabelText(QFileDialog.DialogLabel.FileName, "Nombre de fichero:")
    dialog.setLabelText(QFileDialog.DialogLabel.FileType, "Tipo de archivo:")
    dialog.setLabelText(QFileDialog.DialogLabel.Accept, "Abrir")
    dialog.setLabelText(QFileDialog.DialogLabel.Reject, "Cancelar")
    dialog.resize(920, 580)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        files = dialog.selectedFiles()
        if files:
            return files[0]
    return None


class ImportBookDialog(QDialog):
    """Diálogo de importación oscuro, con arrastrar y soltar y elección de voz."""

    def __init__(self, parent, voices: list[str], default_voice: str):
        super().__init__(parent)
        self.setObjectName("importDialog")
        self.setWindowTitle("Importar libro")
        self.setModal(True)
        self.setAcceptDrops(True)
        self.setMinimumWidth(480)
        self._file: Path | None = None
        self._auto_name = ""
        self._build(voices, default_voice)
        self._update_state()

    def _build(self, voices: list[str], default_voice: str) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(13)

        eyebrow = QLabel("BIBLIOTECA")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Importar un libro")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Crea un proyecto y sus capítulos a partir de un archivo. "
            "Los PDF escaneados se leen con OCR automático."
        )
        subtitle.setObjectName("dialogSub")
        subtitle.setWordWrap(True)
        lay.addWidget(eyebrow)
        lay.addWidget(title)
        lay.addWidget(subtitle)

        self.drop_zone = QFrame()
        self.drop_zone.setObjectName("dropZone")
        dz = QVBoxLayout(self.drop_zone)
        dz.setContentsMargins(18, 16, 18, 16)
        dz.setSpacing(4)
        self.drop_title = QLabel("Arrastra tu libro aquí")
        self.drop_title.setObjectName("dropTitle")
        self.drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_sub = QLabel("o elige un archivo · TXT, MD, DOCX, EPUB o PDF")
        self.drop_sub.setObjectName("dropSub")
        self.drop_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_sub.setWordWrap(True)
        self.choose_btn = QPushButton("Elegir archivo…")
        self.choose_btn.setCursor(Qt.PointingHandCursor)
        self.choose_btn.setFixedHeight(32)
        self.choose_btn.clicked.connect(self._choose_file)
        choose_row = QHBoxLayout()
        choose_row.addStretch(1)
        choose_row.addWidget(self.choose_btn)
        choose_row.addStretch(1)
        dz.addWidget(self.drop_title)
        dz.addWidget(self.drop_sub)
        dz.addSpacing(4)
        dz.addLayout(choose_row)
        lay.addWidget(self.drop_zone)

        form = QHBoxLayout()
        form.setSpacing(12)
        name_col = QVBoxLayout()
        name_col.setSpacing(5)
        name_label = QLabel("NOMBRE DEL PROYECTO")
        name_label.setObjectName("fieldLabel")
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("field")
        self.name_edit.setPlaceholderText("mi_libro")
        name_col.addWidget(name_label)
        name_col.addWidget(self.name_edit)
        form.addLayout(name_col, 3)

        voice_col = QVBoxLayout()
        voice_col.setSpacing(5)
        voice_label = QLabel("VOZ")
        voice_label.setObjectName("fieldLabel")
        self.voice_combo = QComboBox()
        self.voice_combo.setObjectName("field")
        self.voice_combo.addItems(voices)
        if default_voice in voices:
            self.voice_combo.setCurrentText(default_voice)
        voice_col.addWidget(voice_label)
        voice_col.addWidget(self.voice_combo)
        form.addLayout(voice_col, 2)
        lay.addLayout(form)

        self.error = QLabel("")
        self.error.setObjectName("formError")
        self.error.setWordWrap(True)
        lay.addWidget(self.error)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        self.import_btn = QPushButton("Importar")
        self.import_btn.setObjectName("primary")
        self.import_btn.setDefault(True)
        self.import_btn.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.import_btn)
        lay.addLayout(buttons)

        self.name_edit.textChanged.connect(self._update_state)
        self.voice_combo.currentIndexChanged.connect(self._update_state)

    def _choose_file(self) -> None:
        start = str(self._file.parent) if self._file else str(Path.home())
        path = pick_file(self, "Seleccionar libro", start, IMPORT_FILTER)
        if path:
            self._set_file(Path(path))

    def _set_file(self, path: Path) -> None:
        if not path.is_file() or path.suffix.lower() not in IMPORT_EXTS:
            self.error.setText("Formato no soportado. Usa TXT, MD, DOCX, EPUB o PDF.")
            return
        self._file = path
        try:
            size = _fmt_size(path.stat().st_size)
        except OSError:
            size = "archivo local"
        kind = path.suffix.lstrip(".").upper() or "LIBRO"
        self.drop_title.setText(path.name)
        self.drop_sub.setText(f"{size} · {kind} · listo para importar")
        self.drop_zone.setToolTip(str(path))
        self.choose_btn.setText("Cambiar archivo…")
        if not self._auto_name or self.name_edit.text().strip() == self._auto_name:
            slug = re.sub(r"[^A-Za-z0-9_-]", "_", path.stem)[:40] or "libro"
            self.name_edit.setText(slug)
            self._auto_name = slug
        self.error.setText("")
        self._update_state()

    def _update_state(self) -> None:
        has_file = self._file is not None and self._file.is_file()
        name = self.name_edit.text().strip()
        name_ok = bool(re.fullmatch(r"[A-Za-z0-9_-]+", name))
        has_voice = self.voice_combo.count() > 0

        if has_file and not name:
            self.error.setText("Pon un nombre para el proyecto.")
        elif name and not name_ok:
            self.error.setText("El nombre solo admite letras, números, guiones y guion bajo.")
        else:
            self.error.setText("")
        self.import_btn.setEnabled(has_file and name_ok and has_voice)

    def accept(self) -> None:
        self._update_state()
        if not self.import_btn.isEnabled():
            if self._file is None:
                self.error.setText("Elige un libro para importar.")
            return
        super().accept()

    def data(self) -> dict:
        return {
            "path": self._file,
            "name": self.name_edit.text().strip(),
            "voice": self.voice_combo.currentText(),
        }

    def _set_drag(self, active: bool) -> None:
        self.drop_zone.setProperty("dragActive", active)
        self.drop_zone.style().unpolish(self.drop_zone)
        self.drop_zone.style().polish(self.drop_zone)

    def dragEnterEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                if (
                    url.isLocalFile()
                    and Path(url.toLocalFile()).suffix.lower() in IMPORT_EXTS
                ):
                    event.acceptProposedAction()
                    self._set_drag(True)
                    return

    def dragLeaveEvent(self, event) -> None:
        self._set_drag(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._set_drag(False)
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.suffix.lower() in IMPORT_EXTS:
                    self._set_file(path)
                    event.acceptProposedAction()
                    return
        self.error.setText("Arrastra un archivo TXT, MD, DOCX, EPUB o PDF.")




class VoiceAddDialog(QDialog):
    """Alta de una voz con muestra, nombre e idioma."""

    LANGUAGES = (
        ("Español", "es"),
        ("Inglés", "en"),
        ("Francés", "fr"),
        ("Alemán", "de"),
        ("Italiano", "it"),
        ("Portugués", "pt"),
    )

    def __init__(self, parent, existing_names: set[str]):
        super().__init__(parent)
        self.setObjectName("voiceDialog")
        self.setWindowTitle("Añadir voz")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._existing = existing_names
        self._file: Path | None = None
        self._auto_name = ""
        self._build()
        self._update_state()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)

        eyebrow = QLabel("VOCES")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Añadir una voz")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Una muestra limpia de 10-30 segundos, con una sola voz y sin música, "
            "es suficiente para clonar el timbre."
        )
        subtitle.setObjectName("dialogSub")
        subtitle.setWordWrap(True)
        lay.addWidget(eyebrow)
        lay.addWidget(title)
        lay.addWidget(subtitle)

        sample_label = QLabel("MUESTRA DE VOZ")
        sample_label.setObjectName("fieldLabel")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.file_edit = QLineEdit()
        self.file_edit.setObjectName("field")
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText("Ningún archivo seleccionado")
        self.btn_file = QPushButton("Elegir…")
        self.btn_file.setCursor(Qt.PointingHandCursor)
        self.btn_file.clicked.connect(self._choose_file)
        row.addWidget(self.file_edit, 1)
        row.addWidget(self.btn_file)
        lay.addWidget(sample_label)
        lay.addLayout(row)

        form = QHBoxLayout()
        form.setSpacing(12)
        name_col = QVBoxLayout()
        name_col.setSpacing(5)
        name_label = QLabel("NOMBRE")
        name_label.setObjectName("fieldLabel")
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("field")
        self.name_edit.setPlaceholderText("mi_voz")
        name_col.addWidget(name_label)
        name_col.addWidget(self.name_edit)
        form.addLayout(name_col, 3)

        lang_col = QVBoxLayout()
        lang_col.setSpacing(5)
        lang_label = QLabel("IDIOMA")
        lang_label.setObjectName("fieldLabel")
        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("field")
        for label, code in self.LANGUAGES:
            self.lang_combo.addItem(f"{label} ({code})", code)
        lang_col.addWidget(lang_label)
        lang_col.addWidget(self.lang_combo)
        form.addLayout(lang_col, 2)
        lay.addLayout(form)

        self.error = QLabel("")
        self.error.setObjectName("formError")
        self.error.setWordWrap(True)
        lay.addWidget(self.error)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        self.add_btn = QPushButton("Añadir voz")
        self.add_btn.setObjectName("primary")
        self.add_btn.setDefault(True)
        self.add_btn.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.add_btn)
        lay.addLayout(buttons)

        self.name_edit.textChanged.connect(self._update_state)

    def _choose_file(self) -> None:
        start = str(self._file.parent) if self._file else str(Path.home())
        path = pick_file(self, "Elegir muestra de voz", start, VOICE_FILTER)
        if path:
            self._set_file(Path(path))

    def _set_file(self, path: Path) -> None:
        if not path.is_file() or path.suffix.lower() not in VOICE_EXTS:
            self.error.setText("Formato no soportado. Usa WAV, FLAC, MP3, OGG o M4A.")
            return
        self._file = path
        self.file_edit.setText(str(path))
        self.file_edit.setToolTip(str(path))
        if not self._auto_name or self.name_edit.text().strip() == self._auto_name:
            slug = re.sub(r"[^A-Za-z0-9_-]", "_", path.stem)[:40] or "mi_voz"
            self.name_edit.setText(slug)
            self._auto_name = slug
        self.error.setText("")
        self._update_state()

    def _update_state(self) -> None:
        has_file = self._file is not None and self._file.is_file()
        name = self.name_edit.text().strip()
        name_ok = bool(re.fullmatch(r"[A-Za-z0-9_-]+", name))
        if has_file and not name:
            self.error.setText("Pon un nombre para la voz.")
        elif name and not name_ok:
            self.error.setText("El nombre solo admite letras, números, guiones y guion bajo.")
        elif name in self._existing:
            self.error.setText(f"Ya existe una voz llamada «{name}».")
            name_ok = False
        else:
            self.error.setText("")
        self.add_btn.setEnabled(has_file and name_ok)

    def accept(self) -> None:
        self._update_state()
        if self.add_btn.isEnabled():
            super().accept()

    def data(self) -> dict:
        return {
            "path": self._file,
            "name": self.name_edit.text().strip(),
            "language": self.lang_combo.currentData(),
        }




class VoiceManagerDialog(QDialog):
    """Lista, analiza y reproduce los perfiles de voz; permite añadir y borrar."""

    def __init__(self, parent, db_path: Path, data_dir: Path):
        super().__init__(parent)
        self.setObjectName("voiceDialog")
        self.setWindowTitle("Gestión de voces")
        self.setModal(True)
        self.setMinimumSize(700, 500)
        self.db_path = db_path
        self.data_dir = data_dir
        self._profiles: dict[str, dict] = {}
        self._usage: dict[str, list[str]] = {}
        self._qa_cache: dict[str, list] = {}
        self._current: str | None = None
        self._clone_process = None
        self._clone_out: Path | None = None
        self._clone_text: Path | None = None
        self._clone_timer = None
        self._clone_path: Path | None = None
        self._clone_log = ""
        self._analyze_thread = None
        # Servicio de gestión de voces
        self.voice_service = VoiceManagerService(
            store=Store(self.db_path),
            settings=load_settings(self.data_dir),
            data_dir=self.data_dir,
        )
        self._build()
        self._build_player()
        self.reload()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)

        head = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(1)
        eyebrow = QLabel("BIBLIOTECA")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Gestión de voces")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Analiza la calidad de cada muestra, escúchala y decide con cuál narrar."
        )
        subtitle.setObjectName("dialogSub")
        left.addWidget(eyebrow)
        left.addWidget(title)
        left.addWidget(subtitle)
        head.addLayout(left, 1)
        close = QPushButton("Cerrar")
        close.setObjectName("ghost")
        close.clicked.connect(self.accept)
        head.addWidget(close)
        lay.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(14)
        left_widget = QWidget()
        left_panel = QVBoxLayout(left_widget)
        left_panel.setContentsMargins(0, 0, 0, 0)
        left_panel.setSpacing(8)
        row = QHBoxLayout()
        title_list = QLabel("PERFILES")
        title_list.setObjectName("cardTitle")
        self.voice_count = QLabel("0")
        self.voice_count.setObjectName("count")
        row.addWidget(title_list)
        row.addWidget(self.voice_count)
        row.addStretch(1)
        left_panel.addLayout(row)
        self.voices = EmptyList("Todavía no hay voces.\nAñade una muestra para empezar.")
        self.voices.setItemDelegate(CardDelegate(height=56, parent=self.voices))
        self.voices.currentItemChanged.connect(self._show_selected)
        left_panel.addWidget(self.voices, 1)
        self.btn_add_voice = QPushButton("＋  Añadir voz")
        self.btn_add_voice.setObjectName("primary")
        self.btn_add_voice.setMinimumHeight(36)
        self.btn_add_voice.clicked.connect(self._add_voice)
        left_panel.addWidget(self.btn_add_voice)
        left_widget.setMinimumWidth(300)
        left_widget.setMaximumWidth(340)
        body.addWidget(left_widget)

        detail = QFrame()
        detail.setObjectName("voiceDetail")
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(18, 16, 18, 16)
        dl.setSpacing(8)
        self.detail_title = QLabel("Selecciona una voz")
        self.detail_title.setObjectName("voiceName")
        self.detail_path = QLabel("")
        self.detail_path.setObjectName("voicePath")
        self.detail_path.setWordWrap(True)
        self.detail_badge = QLabel("")
        self.detail_badge.setObjectName("badgeInfo")
        badge_row = QHBoxLayout()
        badge_row.addWidget(self.detail_badge)
        badge_row.addStretch(1)
        self.detail_verdict = QLabel("")
        self.detail_verdict.setObjectName("voiceVerdict")
        self.detail_verdict.setWordWrap(True)
        dl.addWidget(self.detail_title)
        dl.addWidget(self.detail_path)
        dl.addLayout(badge_row)
        dl.addWidget(self.detail_verdict)

        metrics_title = QLabel("MÉTRICAS")
        metrics_title.setObjectName("section")
        dl.addWidget(metrics_title)
        self.metrics_layout = QVBoxLayout()
        self.metrics_layout.setSpacing(4)
        dl.addLayout(self.metrics_layout)

        usage_title = QLabel("USO")
        usage_title.setObjectName("section")
        dl.addWidget(usage_title)
        self.detail_usage = QLabel("")
        self.detail_usage.setObjectName("voiceUsage")
        self.detail_usage.setWordWrap(True)
        dl.addWidget(self.detail_usage)
        dl.addStretch(1)

        self.clone_status = QLabel("")
        self.clone_status.setObjectName("voiceUsage")
        self.clone_status.setWordWrap(True)
        dl.addWidget(self.clone_status)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_play_voice = QPushButton("▶  Muestra original")
        self.btn_play_voice.setObjectName("ghost")
        self.btn_play_voice.clicked.connect(self._play_voice)
        self.btn_stop_voice = QPushButton("■  Detener")
        self.btn_stop_voice.setObjectName("ghost")
        self.btn_stop_voice.clicked.connect(self._stop_voice)
        self.btn_clone = QPushButton("Probar clonación 30 s")
        self.btn_clone.setObjectName("primary")
        self.btn_clone.clicked.connect(self._clone_preview)
        self.btn_delete_voice = QPushButton("Eliminar voz")
        self.btn_delete_voice.setObjectName("danger")
        self.btn_delete_voice.clicked.connect(self._delete_voice)
        actions.addWidget(self.btn_play_voice)
        actions.addWidget(self.btn_stop_voice)
        actions.addWidget(self.btn_clone)
        actions.addStretch(1)
        actions.addWidget(self.btn_delete_voice)
        dl.addLayout(actions)
        body.addWidget(detail, 1)
        lay.addLayout(body, 1)

    def _build_player(self) -> None:
        self.preview_player = None
        self.preview_audio = None
        if not HAS_MULTIMEDIA:
            self.btn_play_voice.setEnabled(False)
            self.btn_stop_voice.setEnabled(False)
            return
        self.preview_player = QMediaPlayer(self)
        self.preview_audio = QAudioOutput(self)
        self.preview_player.setAudioOutput(self.preview_audio)
        self.preview_audio.setVolume(0.8)

    def _run_cli(self, args: list[str]) -> tuple[int, str]:
        # DEPRECATED: bloquea el event loop (subprocess.run síncrono). Usar
        # _run_cli_async en su lugar. Borrar en 5.5.
        cmd = [sys.executable, "-m", "voxforge"] + [str(a) for a in args]
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = subprocess.run(
                cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=180
            )
            return res.returncode, (res.stdout or "") + (res.stderr or "")
        except Exception as exc:
            return 1, str(exc)
        finally:
            QApplication.restoreOverrideCursor()

    def reload(self, *, select: str | None = None) -> None:
        previous = select or self._current
        self._qa_cache.clear()
        try:
            store = Store(self.db_path)
            try:
                profiles = [dict(p) for p in store.list_profiles()]
            finally:
                store.close()
            projects = list_projects(self.db_path)
        except Exception as exc:
            QMessageBox.warning(self, "Voces", f"No se pudieron leer las voces:\n{exc}")
            return

        self._profiles = {p["name"]: p for p in profiles}
        self._usage = {}
        for project in projects:
            self._usage.setdefault(project["voice_profile"], []).append(project["name"])

        self.voices.blockSignals(True)
        self.voices.clear()
        for profile in profiles:
            name = profile["name"]
            try:
                duration = sf.info(profile["ref_path"]).duration
                duration_txt = f"{duration:.1f} s"
            except Exception:
                duration_txt = "muestra no disponible"
            used = self._usage.get(name, [])
            usage_txt = f"{len(used)} proyectos" if used else "sin uso"
            it = QListWidgetItem()
            it.setData(ROLE_ID, name)
            it.setData(ROLE_TITLE, name)
            it.setData(ROLE_SUB, f"{profile['language']} · {duration_txt} · {usage_txt}")
            it.setData(ROLE_BADGE, "EN USO" if used else "LIBRE")
            it.setData(ROLE_BADGE_COLOR, AMBER if used else GREEN)
            it.setToolTip(profile["ref_path"])
            self.voices.addItem(it)
        self.voice_count.setText(str(len(profiles)))
        self.voices.blockSignals(False)

        if profiles:
            target = previous if previous in self._profiles else profiles[0]["name"]
            for row in range(self.voices.count()):
                if self.voices.item(row).data(ROLE_ID) == target:
                    self.voices.setCurrentRow(row)
                    break
        else:
            self._show_profile(None)

    def _show_selected(self, current, _previous=None) -> None:
        self._show_profile(current)

    def _show_profile(self, item) -> None:
        if item is None:
            self._current = None
            self.detail_title.setText("Selecciona una voz")
            self.detail_path.setText("")
            self.detail_badge.setText("")
            self.detail_badge.setObjectName("badgeInfo")
            self.detail_badge.style().unpolish(self.detail_badge)
            self.detail_badge.style().polish(self.detail_badge)
            self.detail_verdict.setText("")
            self.detail_usage.setText("")
            self._clear_metrics()
            self.btn_play_voice.setEnabled(False)
            self.btn_stop_voice.setEnabled(False)
            self.btn_clone.setEnabled(False)
            self.btn_delete_voice.setEnabled(False)
            return

        name = item.data(ROLE_ID)
        profile = self._profiles.get(name)
        if profile is None:
            return
        self._current = name
        self.detail_title.setText(name)
        self.detail_path.setText(profile["ref_path"])
        self.btn_delete_voice.setEnabled(True)
        self.btn_play_voice.setEnabled(self.preview_player is not None)
        self.btn_stop_voice.setEnabled(self.preview_player is not None)
        self.btn_clone.setEnabled(self._clone_process is None)

        used = self._usage.get(name, [])
        checks = self._qa_cache.get(name)
        if checks is None:
            # Mostrar estado de análisis y lanzar en hilo de fondo
            self.detail_verdict.setText("Analizando muestra…")
            self.detail_verdict.setStyleSheet(f"color: {MUTED};")
            self._clear_metrics()
            self._analyze_thread = AudioAnalyzeThread(profile["ref_path"], self)
            self._analyze_thread.finished.connect(
                lambda result: self._on_voice_analyzed(name, result)
            )
            self._analyze_thread.start()
            # badge/usage se actualizan en _on_voice_analyzed
            suffix = " · EN USO" if used else ""
            self.detail_badge.setText("ANALIZANDO" + suffix)
            self.detail_badge.setObjectName("badgeInfo")
            self.detail_badge.style().unpolish(self.detail_badge)
            self.detail_badge.style().polish(self.detail_badge)
            if used:
                self.detail_usage.setText("Proyectos que la usan: " + ", ".join(used))
            else:
                self.detail_usage.setText("Ningún proyecto usa esta voz todavía.")
            return

        self._apply_voice_analysis(name, profile, checks, used)

    def _on_voice_analyzed(self, name: str, checks: list) -> None:
        """Callback cuando el hilo de fondo termina de analizar la muestra."""
        self._qa_cache[name] = checks
        profile = self._profiles.get(name)
        if profile is None:
            return
        used = self._usage.get(name, [])
        self._apply_voice_analysis(name, profile, checks, used)

    def _apply_voice_analysis(self, name: str, profile: dict, checks: list, used: list[str]) -> None:
        """Aplica el resultado del análisis de voz a la UI del detalle."""
        if checks:
            statuses = {c.status for c in checks}
            if "MAL" in statuses:
                color, badge_text, badge_obj = RED, "REVISAR", "badgeBad"
            elif "AVISO" in statuses:
                color, badge_text, badge_obj = AMBER, "MEJORABLE", "badgeWarn"
            else:
                color, badge_text, badge_obj = GREEN, "BUENA", "badgeOk"
            self.detail_verdict.setText(verdict(checks))
            self.detail_verdict.setStyleSheet(f"color: {color};")
            self._fill_metrics(checks, profile)
        else:
            color, badge_text, badge_obj = MUTED, "SIN ANÁLISIS", "badgeInfo"
            self.detail_verdict.setText("No se pudo analizar la muestra.")
            self.detail_verdict.setStyleSheet(f"color: {RED};")
            self._clear_metrics()

        suffix = " · EN USO" if used else ""
        self.detail_badge.setText(f"{badge_text}{suffix}")
        self.detail_badge.setObjectName(badge_obj)
        self.detail_badge.style().unpolish(self.detail_badge)
        self.detail_badge.style().polish(self.detail_badge)

        if used:
            self.detail_usage.setText("Proyectos que la usan: " + ", ".join(used))
        else:
            self.detail_usage.setText("Ningún proyecto usa esta voz todavía.")

    def _clear_metrics(self) -> None:
        while self.metrics_layout.count():
            item = self.metrics_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _fill_metrics(self, checks, profile: dict) -> None:
        self._clear_metrics()
        try:
            store = Store(self.db_path)
            try:
                cached = store.conn.execute(
                    "SELECT COUNT(*) FROM fragments WHERE profile_id = ?",
                    (profile["id"],),
                ).fetchone()[0]
            finally:
                store.close()
        except Exception:
            cached = 0

        rows = [("Caché", f"{_fmt_int(cached)} fragmentos")]
        rows.extend((c.name, c.value) for c in checks)
        for name, value in rows:
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(8)
            key = QLabel(name)
            key.setObjectName("metricName")
            val = QLabel(value)
            val.setObjectName("metricValue")
            hl.addWidget(key, 1)
            hl.addWidget(val)
            self.metrics_layout.addWidget(row)

    def _play_voice(self) -> None:
        if self.preview_player is None or not self._current:
            return
        profile = self._profiles.get(self._current)
        if profile is None or not Path(profile["ref_path"]).is_file():
            QMessageBox.warning(self, "Voz", "La muestra de esta voz no está disponible.")
            return
        self._cancel_clone_timer()
        self.preview_player.setSource(QUrl.fromLocalFile(profile["ref_path"]))
        self.preview_player.play()
        self.clone_status.setText("Reproduciendo la muestra original.")

    def _stop_voice(self) -> None:
        if self.preview_player:
            self.preview_player.stop()
        self._cancel_clone_timer()
        self.clone_status.setText("")

    def _cancel_clone_timer(self) -> None:
        if self._clone_timer is not None:
            self._clone_timer.stop()
            self._clone_timer = None
        self._clone_path = None

    def _clone_preview(self) -> None:
        if self._clone_process is not None or not self._current:
            return
        profile = self._profiles.get(self._current)
        if profile is None:
            return
        name = self._current
        demo = (
            "La voz clonada conserva el timbre y la entonación de la muestra original. "
            "Escucha esta frase de prueba para decidir si la voz encaja con tu proyecto. "
            "Después podrás narrar capítulos completos o previsualizar solo los primeros treinta segundos."
        )
        preview_dir = self.data_dir / "exports" / "_voice_previews"
        preview_dir.mkdir(parents=True, exist_ok=True)
        out_path = preview_dir / f"{name}_clon30.wav"
        text_dir = self.data_dir / "imports"
        text_dir.mkdir(parents=True, exist_ok=True)
        text_path = text_dir / f"_voice_preview_{name}.txt"
        text_path.write_text(demo, encoding="utf-8")

        self._clone_out = out_path
        self._clone_text = text_path
        self._clone_log = ""
        self.btn_clone.setEnabled(False)
        self.btn_clone.setText("Generando…")
        self.clone_status.setText("Generando la clonación; la primera carga del modelo puede tardar.")

        process = QProcess(self)
        process.setWorkingDirectory(str(ROOT))
        env = QProcessEnvironment.systemEnvironment()
        env.insert("VOXFORGE_HOME", str(self.data_dir))
        process.setProcessEnvironment(env)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._clone_read)
        process.finished.connect(self._clone_finished)
        process.errorOccurred.connect(self._clone_error)
        process.start(
            sys.executable,
            [
                "-m", "voxforge", "speak", str(text_path),
                "--voice", name,
                "--out", str(out_path),
                "--language", str(profile.get("language") or "es"),
            ],
        )
        self._clone_process = process

    def _clone_read(self) -> None:
        process = self._clone_process
        if process is None:
            return
        data = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if not data:
            return
        self._clone_log += data
        frags = re.findall(r"\[(\d+)/(\d+)\]", self._clone_log)
        if frags:
            current, total = frags[-1]
            self.clone_status.setText(f"Generando clonación… {current}/{total} fragmentos")

    def _clone_error(self, _error) -> None:
        if self._clone_process is not None:
            self.btn_clone.setEnabled(True)
            self.btn_clone.setText("Probar clonación 30 s")
            self.clone_status.setText("No se pudo iniciar la generación de la clonación.")
            self._clone_process = None

    def _clone_finished(self, exit_code: int, _status) -> None:
        process = self._clone_process
        self._clone_process = None
        out_path = self._clone_out
        text_path = self._clone_text
        self._clone_out = None
        self._clone_text = None
        if text_path is not None:
            text_path.unlink(missing_ok=True)

        self.btn_clone.setEnabled(True)
        self.btn_clone.setText("Probar clonación 30 s")
        if exit_code != 0 or out_path is None or not out_path.is_file():
            detail = self._clone_log.strip().splitlines()[-1:] or []
            self.clone_status.setText(
                "No se pudo generar la clonación." + (f" {detail[0]}" if detail else "")
            )
            return
        if self.preview_player is None:
            self.clone_status.setText("Clonación generada, pero QtMultimedia no está disponible.")
            return
        self._cancel_clone_timer()
        self._clone_path = out_path
        self.preview_player.setSource(QUrl.fromLocalFile(str(out_path)))
        self.preview_player.play()
        self.clone_status.setText("Reproduciendo 30 segundos de la voz clonada.")
        self._clone_timer = QTimer(self)
        self._clone_timer.setSingleShot(True)
        self._clone_timer.timeout.connect(self._stop_clone_playback)
        self._clone_timer.start(30_000)

    def _stop_clone_playback(self) -> None:
        if self._clone_timer is not None:
            self._clone_timer.stop()
            self._clone_timer = None
        if (
            self.preview_player is not None
            and self._clone_path is not None
            and Path(self.preview_player.source().toLocalFile()) == self._clone_path
        ):
            self.preview_player.stop()
        self._clone_path = None


    def _add_voice(self) -> None:
        dialog = VoiceAddDialog(self, set(self._profiles))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.data()
        
        # Usar VoiceManagerService en lugar de _run_cli
        from voxforge.services import VoiceProfileRequest
        request = VoiceProfileRequest(
            name=data["name"],
            reference_path=Path(data["path"]),
            language=data["language"]
        )
        response = self.voice_service.create_profile(request)
        
        if not response.success:
            QMessageBox.warning(self, "No se pudo añadir la voz", response.error or "Error desconocido.")
            return
        self.reload(select=data["name"])

    def _delete_voice(self) -> None:
        if not self._current:
            return
        name = self._current
        used = self._usage.get(name, [])
        if used:
            detail = "\n\nEstos proyectos se quedarán apuntando a una voz inexistente:\n" + ", ".join(used)
            title = "Voz en uso"
        else:
            detail = "\n\nSe eliminará la muestra y su caché de voz."
            title = "Eliminar voz"
        resp = QMessageBox.question(
            self, title,
            f"¿Eliminar la voz «{name}»?{detail}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        
        # Usar VoiceManagerService en lugar de _run_cli
        response = self.voice_service.delete_profile(name)
        if not response.success:
            QMessageBox.warning(self, "No se pudo eliminar", response.error or "Error desconocido.")
            return
        self.reload()

    def done(self, result: int) -> None:
        if self._clone_process is not None:
            self._clone_process.kill()
            self._clone_process.waitForFinished(1000)
            self._clone_process = None
        if self._clone_text is not None:
            self._clone_text.unlink(missing_ok=True)
            self._clone_text = None
        self._cancel_clone_timer()
        if self._analyze_thread is not None:
            self._analyze_thread.quit()
            self._analyze_thread.wait(1000)
            self._analyze_thread = None
        if self.preview_player:
            self.preview_player.stop()
        super().done(result)

    def closeEvent(self, event) -> None:
        if self._clone_process is not None:
            self._clone_process.kill()
            self._clone_process.waitForFinished(1000)
            self._clone_process = None
        if self._clone_text is not None:
            self._clone_text.unlink(missing_ok=True)
            self._clone_text = None
        self._cancel_clone_timer()
        if self._analyze_thread is not None:
            self._analyze_thread.quit()
            self._analyze_thread.wait(1000)
            self._analyze_thread = None
        if self.preview_player:
            self.preview_player.stop()
        super().closeEvent(event)




class ChapterEditorDialog(QDialog):
    """Edita título y texto del capítulo, valida pausas y muestra el coste estimado."""

    def __init__(self, parent, project: str, chapter: dict, settings):
        super().__init__(parent)
        self.setObjectName("editorDialog")
        self.setWindowTitle(f"Editar capítulo · {project}")
        self.setModal(True)
        self.setMinimumSize(700, 500)
        self.project = project
        self.ordinal = int(chapter["ordinal"])
        self.settings = settings
        self._original_title = chapter["title"]
        self._original_text = chapter["text"]
        self._dirty = False
        self._narrate = False
        self._build()
        self._validate_timer = QTimer(self)
        self._validate_timer.setSingleShot(True)
        self._validate_timer.timeout.connect(self._validate)
        self._validate()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)

        eyebrow = QLabel("EDITOR")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Editar capítulo")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            f"{self.project} · capítulo {self.ordinal:02d}. "
            "Los cambios se guardan en el proyecto y los fragmentos se recalculan al narrar."
        )
        subtitle.setObjectName("dialogSub")
        subtitle.setWordWrap(True)
        lay.addWidget(eyebrow)
        lay.addWidget(title)
        lay.addWidget(subtitle)

        title_label = QLabel("TÍTULO")
        title_label.setObjectName("fieldLabel")
        self.title_edit = QLineEdit(self._original_title)
        self.title_edit.setObjectName("field")
        lay.addWidget(title_label)
        lay.addWidget(self.title_edit)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(7)
        insert_label = QLabel("INSERTAR")
        insert_label.setObjectName("fieldLabel")
        toolbar.addWidget(insert_label)
        for text, marker in (
            ("Pausa 1,5 s", " [pausa=1.5s] "),
            ("Pausa 3 s", " [pausa=3s] "),
            ("Silencio 2 s", " [silencio=2s] "),
        ):
            button = QPushButton(text)
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip("Inserta una marca de pausa en el cursor")
            button.clicked.connect(lambda _checked=False, m=marker: self._insert(m))
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        self.stats = QLabel("")
        self.stats.setObjectName("editorStats")
        toolbar.addWidget(self.stats)
        lay.addLayout(toolbar)

        find_row = QHBoxLayout()
        find_row.setSpacing(7)
        self.find_edit = QLineEdit()
        self.find_edit.setObjectName("search")
        self.find_edit.setPlaceholderText("Buscar en el capítulo…")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.setMinimumWidth(150)
        self.find_edit.setToolTip("La búsqueda distingue mayúsculas y minúsculas")
        find_button = QPushButton("Buscar")
        find_button.clicked.connect(self._find_next)
        self.replace_edit = QLineEdit()
        self.replace_edit.setObjectName("search")
        self.replace_edit.setPlaceholderText("Reemplazar por…")
        self.replace_edit.setClearButtonEnabled(True)
        self.replace_edit.setMinimumWidth(150)
        replace_button = QPushButton("Reemplazar todo")
        replace_button.clicked.connect(self._replace_all)
        self.find_status = QLabel("")
        self.find_status.setObjectName("count")
        find_row.addWidget(self.find_edit, 1)
        find_row.addWidget(find_button)
        find_row.addWidget(self.replace_edit, 1)
        find_row.addWidget(replace_button)
        find_row.addWidget(self.find_status)
        lay.addLayout(find_row)

        self.editor = QPlainTextEdit()
        self.editor.setObjectName("chapterEditor")
        self.editor.setPlaceholderText("El texto del capítulo aparecerá aquí…")
        self.editor.setPlainText(self._original_text)
        lay.addWidget(self.editor, 1)

        self.error = QLabel("")
        self.error.setObjectName("formError")
        self.error.setWordWrap(True)
        lay.addWidget(self.error)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.dirty_label = QLabel("Sin cambios")
        self.dirty_label.setObjectName("count")
        bottom.addWidget(self.dirty_label)
        bottom.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("Guardar")
        self.btn_save.clicked.connect(lambda: self._save(False))
        self.btn_save_narrate = QPushButton("Guardar y narrar")
        self.btn_save_narrate.setObjectName("primary")
        self.btn_save_narrate.clicked.connect(lambda: self._save(True))
        bottom.addWidget(cancel)
        bottom.addWidget(self.btn_save)
        bottom.addWidget(self.btn_save_narrate)
        lay.addLayout(bottom)

        self.title_edit.textChanged.connect(self._changed)
        self.editor.textChanged.connect(self._changed)
        self._shortcuts = []
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(lambda: self._save(False))
        self._shortcuts.append(save_shortcut)
        for sequence, handler in (("Ctrl+F", self._focus_find), ("Ctrl+H", self._focus_replace)):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    def _insert(self, marker: str) -> None:
        cursor = self.editor.textCursor()
        cursor.insertText(marker)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _focus_find(self) -> None:
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def _focus_replace(self) -> None:
        self.replace_edit.setFocus()
        self.replace_edit.selectAll()

    def _find_next(self) -> None:
        term = self.find_edit.text().strip()
        if not term:
            self.find_edit.setFocus()
            return
        if self.editor.find(term):
            self.find_status.setText("Encontrado")
            return
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        if self.editor.find(term):
            self.find_status.setText("Búsqueda reiniciada")
        else:
            self.find_status.setText("Sin coincidencias")

    def _replace_all(self) -> None:
        term = self.find_edit.text().strip()
        replacement = self.replace_edit.text()
        if not term:
            self.find_edit.setFocus()
            return
        if term == replacement:
            self.find_status.setText("Buscar y reemplazar son iguales")
            return
        if term in replacement:
            self.find_status.setText("El reemplazo contiene el texto buscado")
            return
        document = self.editor.document()
        cursor = QTextCursor(document)
        count = 0
        cursor.beginEditBlock()
        try:
            while True:
                found = document.find(term, cursor)
                if found.isNull():
                    break
                found.insertText(replacement)
                cursor = found
                count += 1
        finally:
            cursor.endEditBlock()
        self.find_status.setText(f"{_plural(count, 'reemplazo', 'reemplazos')}")

    def _changed(self) -> None:
        self._dirty = (
            self.title_edit.text() != self._original_title
            or self.editor.toPlainText() != self._original_text
        )
        self.dirty_label.setText("Cambios sin guardar" if self._dirty else "Sin cambios")
        self._validate_timer.start(180)

    def _validate(self) -> bool:
        title = self.title_edit.text().strip()
        text = self.editor.toPlainText()
        if not title:
            self.error.setText("El título no puede estar vacío.")
            self.stats.setText("")
            self.btn_save.setEnabled(False)
            self.btn_save_narrate.setEnabled(False)
            return False
        if not text.strip():
            self.error.setText("El texto no puede estar vacío.")
            self.stats.setText("")
            self.btn_save.setEnabled(False)
            self.btn_save_narrate.setEnabled(False)
            return False
        try:
            segments = split_segments(text, self.settings.max_chunk_chars)
        except PauseError as exc:
            self.error.setText(f"Pausas: {exc}")
            self.stats.setText("")
            self.btn_save.setEnabled(False)
            self.btn_save_narrate.setEnabled(False)
            return False
        text_count = sum(1 for s in segments if s.kind == "text")
        pause_count = len(segments) - text_count
        chars = len(text)
        self.error.setText("" if text_count else "El capítulo no contiene texto narrable.")
        self.stats.setText(
            f"{_fmt_int(chars)} caracteres · {_plural(text_count, 'fragmento', 'fragmentos')}"
            f" · {_plural(pause_count, 'pausa', 'pausas')} · {_fmt_char_minutes(chars)}"
        )
        valid = text_count > 0
        self.btn_save.setEnabled(valid)
        self.btn_save_narrate.setEnabled(valid)
        return valid

    def _save(self, narrate: bool) -> None:
        self._validate_timer.stop()
        if not self._validate():
            return
        self._narrate = narrate
        super().accept()

    def reject(self) -> None:
        if self._dirty:
            resp = QMessageBox.question(
                self,
                "Descartar cambios",
                "Hay cambios sin guardar en el capítulo. ¿Descartarlos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return
        super().reject()

    def data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "text": self.editor.toPlainText(),
            "narrate": self._narrate,
        }


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _fmt_ms(ms: int) -> str:
    if ms < 0:
        ms = 0
    s = ms // 1000
    return f"{s // 60:d}:{s % 60:02d}"


def _fmt_int(value: float | int) -> str:
    """Número con separador de miles español (44.173)."""
    return f"{int(value):,}".replace(",", ".")


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{_fmt_int(n)} {singular if int(n) == 1 else plural}"


def _fmt_char_minutes(chars: int) -> str:
    minutes = max(0, chars) / 10 / 60
    return "<1 min" if minutes < 1 else f"~{minutes:.0f} min"


def _fmt_size(num_bytes: int) -> str:
    size = float(max(num_bytes, 0))
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _fmt_ago(timestamp: float) -> str:
    delta = max(0.0, datetime.now().timestamp() - timestamp)
    if delta < 60:
        return "ahora"
    if delta < 3600:
        return f"hace {int(delta // 60)} min"
    if delta < 86400:
        return f"hace {int(delta // 3600)} h"
    if delta < 86400 * 7:
        return f"hace {int(delta // 86400)} d"
    return datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y")


def _fmt_clock(seconds: float) -> str:
    s = max(0, int(seconds))
    hours, rem = divmod(s, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0.0, float(seconds))
    if seconds < 45:
        return f"{int(round(seconds))} s"
    minutes = int(round(seconds / 60))
    if minutes < 60:
        return f"{minutes} min"
    hours, mins = divmod(minutes, 60)
    return f"{hours} h {mins:02d} min" if mins else f"{hours} h"


def _parse_job_time(value) -> datetime | None:
    if not value:
        return None
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _job_elapsed(job: dict) -> float:
    start = _parse_job_time(job.get("started_at") or job.get("created_at"))
    if start is None:
        return 0.0
    end = _parse_job_time(job.get("finished_at")) or datetime.now(timezone.utc)
    return max(0.0, (end - start).total_seconds())


def _status_style(status: str) -> tuple[str, str]:
    return {
        "running": ("En curso", CYAN),
        "pending": ("En cola", BLUE),
        "succeeded": ("Completado", GREEN),
        "failed": ("Fallido", RED),
        "canceled": ("Cancelado", AMBER),
        "lost": ("Perdido", RED),
    }.get(status, (status.capitalize(), MUTED))


def _cpu_class(temp):
    if temp is None:
        return "badgeInfo", "CPU sin sensor"
    if temp >= 85:
        return "badgeBad", f"CPU {temp:.0f}°C"
    if temp >= 70:
        return "badgeWarn", f"CPU {temp:.0f}°C"
    return "badgeOk", f"CPU {temp:.0f}°C"


class VoxForgeGUI(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        
        # Configurar ventana NOVA Cyberpunk con controles personalizados
        # Hacer ventana frameless para quitar el header del sistema
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
        )
        
        # Habilitar arrastre de ventana (para moverla sin barra de título)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._drag_pos = None
        self._drag_start = None
        self._drag_threshold = 6  # px de tolerancia antes de empezar a arrastrar
        
        self.setWindowTitle("VoxForge · Estudio de narración local")
        self.setMinimumSize(700, 500)
        
        # Añadir botones de control personalizados
        self._setup_window_controls()

        self.data_dir = home()
        self.db_path = self.data_dir / "voxforge.db"
        self.settings = load_settings(self.data_dir)
        self.job_store = JobStore(self.db_path, self.data_dir)
        self.store = Store(self.db_path)
        
        # Inicializar servicios
        self.project_service = ProjectService(
            store=self.store,
            settings=self.settings,
            data_dir=self.data_dir
        )
        self.voice_service = VoiceManagerService(
            store=self.store,
            settings=self.settings,
            data_dir=self.data_dir
        )
        self.narrator_service = NarratorService(
            store=self.store,
            settings=self.settings,
            data_dir=self.data_dir,
            cache_dir=self.data_dir / "cache",
            export_dir=self.data_dir / "exports"
        )

        self.current_project: str | None = None
        self.current_chapter: int | None = None
        self.selected_job_id: int | None = None
        self.selected_fragment: int | None = None
        self.show_all_exports = False
        self.now_playing: Path | None = None
        self._current_theme: str = getattr(self.settings, "theme", DEFAULT_THEME)

        self._projects: dict = {}
        self._chapters: dict = {}
        self._fragment_entries: list = []
        self._frag_stats: tuple[int, int] = (0, 0)
        self._frag_key = None
        self._job_snapshot: dict = {}
        self._last_log_text = ""
        self._prog_base_text = ""
        self._prog_indeterminate = False
        self._seeking = False
        self.fx_preset = ""
        self._preview_jobs: dict[int, dict] = {}
        self._preview_path: Path | None = None
        self._preview_timer = None
        self._procs: set[QProcess] = set()
        self._busy = False

        self._marquee_val = 0
        self._marquee_dir = 1
        self._shimmer = 0
        self._running = False
        self._job_start_time: float | None = None
        self._eta_timer = QTimer(self)
        self._eta_timer.timeout.connect(self._tick_eta)
        self._eta_timer.setInterval(500)

        self._build_ui()
        self._build_player()
        self.refresh_all()

        self.tail_timer = QTimer(self)
        self.tail_timer.timeout.connect(self._tick)
        self.tail_timer.setInterval(REFRESH_IDLE_MS)
        self.tail_timer.start()

        self.fx_timer = QTimer(self)
        self.fx_timer.timeout.connect(self._fx_tick)
        self.fx_timer.setInterval(FX_MS)

    def closeEvent(self, event) -> None:
        # Cierre limpio de QProcess en vuelo (CA-5)
        for proc in list(self._procs):
            proc.kill()
            proc.waitForFinished(1000)
            proc.deleteLater()
        self._procs.clear()
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    # Window Controls (NOVA Cyberpunk Theme)                             #
    # ------------------------------------------------------------------ #

    def _setup_window_controls(self) -> None:
        """Configurar botones de control de ventana personalizados."""
        # Habilitar arrastre de ventana para moverla
        self.setMouseTracking(True)
        
        # Conectar eventos para manejar el arrastre
        self.installEventFilter(self)
        
        # Estado inicial
        self._is_maximized = False

    def _toggle_maximize(self) -> None:
        """Alternar entre maximizado y restaurado."""
        if self.isMaximized():
            self.showNormal()
            self._is_maximized = False
            self.btn_maximize.setText("□")
        else:
            self.showMaximized()
            self._is_maximized = True
            self.btn_maximize.setText("⛶")

    def changeEvent(self, event) -> None:
        """Manejar cambios de estado de la ventana."""
        if event.type() == event.Type.WindowStateChange:
            if self.isMaximized():
                self._is_maximized = True
                self.btn_maximize.setText("⛶")
            else:
                self._is_maximized = False
                self.btn_maximize.setText("□")
        super().changeEvent(event)

    def _clamp_to_screen(self, pos: QPoint) -> None:
        """Evita que la ventana se salga de los límites del escritorio."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.move(pos)
            return
        geo = screen.availableGeometry()
        x = max(geo.left(), min(pos.x(), geo.right() - self.width()))
        y = max(geo.top(), min(pos.y(), geo.bottom() - self.height()))
        self.move(QPoint(x, y))

    def eventFilter(self, obj, event) -> bool:
        """Manejar eventos de mouse para arrastrar la ventana."""
        if obj is self and event.type() == event.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint()
                self._drag_start = self._drag_pos
            return False  # dejamos que los hijos procesen el clic
        elif obj is self and event.type() == event.Type.MouseMove:
            if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
                # Ignorar movimientos menores al umbral (evita arrastrar al hacer clic)
                if self._drag_start is not None:
                    delta = event.globalPosition().toPoint() - self._drag_start
                    if abs(delta.x()) < self._drag_threshold and abs(delta.y()) < self._drag_threshold:
                        return False
                new_pos = self.pos() + event.globalPosition().toPoint() - self._drag_pos
                self._clamp_to_screen(new_pos)
                self._drag_pos = event.globalPosition().toPoint()
                return True
        elif obj is self and event.type() == event.Type.MouseButtonRelease:
            self._drag_pos = None
            self._drag_start = None
            return False
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event) -> None:
        """Manejar clic de mouse para cerrar/minimizar/maximizar."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            self._drag_start = self._drag_pos
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Manejar movimiento de mouse para arrastrar ventana."""
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            # Ignorar movimientos menores al umbral (evita arrastrar al hacer clic)
            if self._drag_start is not None:
                delta = event.globalPosition().toPoint() - self._drag_start
                if abs(delta.x()) < self._drag_threshold and abs(delta.y()) < self._drag_threshold:
                    super().mouseMoveEvent(event)
                    return
            new_pos = self.pos() + event.globalPosition().toPoint() - self._drag_pos
            self._clamp_to_screen(new_pos)
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Liberar posición de arrastre."""
        self._drag_pos = None
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        """Manejar atajos de teclado."""
        # ESC para cerrar
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ #
    # UI                                                                  #
    # ------------------------------------------------------------------ #

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setObjectName("section")
        return lbl

    def _badge(self, obj: str, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName(obj)
        return lbl

    def _btn(self, text: str, obj: str, tip: str) -> QPushButton:
        b = QPushButton(text)
        if obj:
            b.setObjectName(obj)
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def _section_row(self, text: str, count_label: QLabel, extra=None) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(6)
        row.addWidget(self._section(text))
        row.addStretch(1)
        row.addWidget(count_label)
        if extra is not None:
            row.addWidget(extra)
        return row

    def _build_ui(self) -> None:
        # Crear widget contenedor principal con barra de título
        container = QWidget()
        container.setObjectName("nova_container")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Crear barra de título personalizada con botones de control
        title_bar = self._build_title_bar()
        container_layout.addWidget(title_bar)
        
        # Crear el contenido principal
        central = QWidget()
        central.setObjectName("central")
        container_layout.addWidget(central, 1)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        main = QWidget()
        main.setObjectName("main")
        ml = QVBoxLayout(main)
        ml.setContentsMargins(16, 14, 16, 12)
        ml.setSpacing(10)
        ml.addWidget(self._build_context())
        self.content_stack = QStackedWidget()
        self.welcome_page = self._build_welcome()
        self.workspace = self._build_content()
        self.content_stack.addWidget(self.welcome_page)
        self.content_stack.addWidget(self.workspace)
        ml.addWidget(self.content_stack, 1)
        ml.addWidget(self._build_player_bar())
        root.addWidget(main, 1)

        # Establecer el widget contenedor como central
        self.setCentralWidget(container)

        self._wire_signals()
        self._build_shortcuts()

        self.statusBar().showMessage("Listo")
        hint = QLabel("Ctrl+F buscar  ·  Espacio reproducir")
        hint.setObjectName("hint")
        self.statusBar().addPermanentWidget(hint)

    def _build_title_bar(self) -> QWidget:
        """Crear barra de título personalizada con botones de control."""
        title_bar = QWidget()
        title_bar.setObjectName("title_bar")
        title_bar.setFixedHeight(40)
        
        # Layout de la barra de título
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)
        
        # Título de la ventana (puede ser actualizado dinámicamente)
        self.title_label = QLabel("VoxForge · Estudio de narración local")
        self.title_label.setObjectName("title_label")
        self.title_label.setStyleSheet(
            "color: #00ffff; font-size: 13px; font-weight: 600;"
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.title_label, 1)
        
        # Espaciador para separar el título de los controles
        layout.addSpacing(8)
        
        # Botones de control (derecha)
        control_layout = QHBoxLayout()
        control_layout.setSpacing(5)
        
        # Botón de minimizar
        self.btn_minimize = QPushButton("_")
        self.btn_minimize.setObjectName("btn_minimize")
        self.btn_minimize.setFixedSize(30, 30)
        self.btn_minimize.setToolTip("Minimizar")
        self.btn_minimize.clicked.connect(self.showMinimized)
        control_layout.addWidget(self.btn_minimize)
        
        # Botón de maximizar
        self.btn_maximize = QPushButton("□")
        self.btn_maximize.setObjectName("btn_maximize")
        self.btn_maximize.setFixedSize(30, 30)
        self.btn_maximize.setToolTip("Maximizar")
        self.btn_maximize.clicked.connect(self._toggle_maximize)
        control_layout.addWidget(self.btn_maximize)
        
        # Botón de cerrar
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("btn_close")
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setToolTip("Cerrar")
        self.btn_close.clicked.connect(self.close)
        control_layout.addWidget(self.btn_close)
        
        layout.addLayout(control_layout)
        
        return title_bar

    # ------------------------------------------------------------------ #
    # Barra lateral                                                       #
    # ------------------------------------------------------------------ #

    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        side.setMinimumWidth(160)
        side.setMaximumWidth(400)

        lay = QVBoxLayout(side)
        lay.setContentsMargins(14, 16, 14, 12)
        lay.setSpacing(9)

        head = QHBoxLayout()
        head.setSpacing(10)
        logo = QLabel("V")
        logo.setObjectName("logo")
        logo.setFixedSize(38, 38)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        names = QVBoxLayout()
        names.setSpacing(0)
        brand = QLabel("VOXFORGE")
        brand.setObjectName("brand")
        sub = QLabel("NARRACIÓN LOCAL")
        sub.setObjectName("brandSub")
        names.addWidget(brand)
        names.addWidget(sub)
        head.addWidget(logo)
        head.addLayout(names, 1)
        lay.addLayout(head)

        self.btn_import = self._btn(
            "＋  Importar libro", "primary",
            "Importar TXT/MD/DOCX/EPUB/PDF, trocearlo y crear el proyecto",
        )
        self.btn_import.setMinimumHeight(38)
        lay.addWidget(self.btn_import)

        self.lbl_proj_count = QLabel("0")
        self.lbl_proj_count.setObjectName("count")
        lay.addLayout(self._section_row("Proyectos", self.lbl_proj_count))
        self.projects = EmptyList(
            "Aún no hay proyectos.\nImporta un libro para crear el primero."
        )
        self.projects.setItemDelegate(CardDelegate(height=54, parent=self.projects))
        self.projects.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.projects.setMinimumHeight(80)
        lay.addWidget(self.projects, 1)

        self.lbl_chap_count = QLabel("0")
        self.lbl_chap_count.setObjectName("count")
        self.btn_edit_chapter = self._btn(
            "✎ Editar", "ghost", "Editar el capítulo seleccionado (Ctrl+E)"
        )
        self.btn_edit_chapter.setFixedHeight(26)
        lay.addLayout(
            self._section_row("Capítulos", self.lbl_chap_count, extra=self.btn_edit_chapter)
        )
        self.chapters = EmptyList("Selecciona un proyecto para ver sus capítulos.")
        self.chapters.setItemDelegate(CardDelegate(height=54, parent=self.chapters))
        self.chapters.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chapters.setMinimumHeight(80)
        lay.addWidget(self.chapters, 1)

        guide = QFrame()
        guide.setObjectName("sideCard")
        self.guide_card = guide
        gl = QVBoxLayout(guide)
        gl.setContentsMargins(11, 9, 11, 9)
        gl.setSpacing(3)
        guide_title = QLabel("FLUJO DE TRABAJO")
        guide_title.setObjectName("section")
        gl.addWidget(guide_title)
        for step in (
            "1 · Importa un libro",
            "2 · Elige un capítulo",
            "3 · Narra o regenera",
        ):
            label = QLabel(step)
            label.setObjectName("sideStep")
            gl.addWidget(label)
        lay.addWidget(guide)

        foot = QLabel("v0.6  ·  100 % local  ·  sin nube")
        foot.setObjectName("sidebarFoot")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(foot)
        return side

    # ------------------------------------------------------------------ #
    # Cabecera contextual                                                 #
    # ------------------------------------------------------------------ #

    def _build_context(self) -> QFrame:
        card = QFrame()
        card.setObjectName("context")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(1)
        self.ctx_eyebrow = QLabel("BIBLIOTECA")
        self.ctx_eyebrow.setObjectName("eyebrow")
        self.ctx_title = QLabel("Sin proyecto")
        self.ctx_title.setObjectName("title")
        self.ctx_sub = QLabel("Importa un libro para empezar · TXT, DOCX, EPUB o PDF")
        self.ctx_sub.setObjectName("subtitle")
        left.addWidget(self.ctx_eyebrow)
        left.addWidget(self.ctx_title)
        left.addWidget(self.ctx_sub)
        top.addLayout(left, 1)

        badges = QHBoxLayout()
        badges.setSpacing(6)
        self.badge_voices = self._badge("badgeInfo", "0 voces")
        self.badge_voices.setToolTip("Perfiles de voz disponibles")
        self.badge_cache = self._badge("badgeInfo", "0 en caché")
        self.badge_cache.setToolTip("Fragmentos de audio reutilizables")
        self.badge_cpu = self._badge("badgeOk", "CPU –")
        self.badge_cpu.setToolTip("Temperatura actual de la CPU")
        self.btn_refresh = self._btn("⟳", "icon", "Refrescar estado (Ctrl+R)")
        self.btn_refresh.setFixedSize(30, 30)
        self.btn_voices = self._btn("Voces", "ghost", "Gestionar perfiles de voz")
        self.btn_voices.setFixedHeight(26)
        for widget in (
            self.badge_voices, self.badge_cache, self.badge_cpu,
            self.btn_voices, self.btn_refresh,
        ):
            widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            if widget not in (self.btn_refresh, self.btn_voices):
                widget.setFixedHeight(26)
            badges.addWidget(widget)
        top.addLayout(badges)
        lay.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_voice = QLabel("voz · —")
        self.chip_voice.setObjectName("chip")
        self.chip_chars = QLabel("0 car.")
        self.chip_chars.setObjectName("chip")
        self.chip_frags = QLabel("0 fragmentos")
        self.chip_frags.setObjectName("chip")
        for chip in (self.chip_voice, self.chip_chars, self.chip_frags):
            chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            chip.setFixedHeight(24)
            chips.addWidget(chip)
        chips.addStretch(1)
        bottom.addLayout(chips, 1)

        actions = QHBoxLayout()
        actions.setSpacing(7)
        self.btn_preview = self._btn(
            "▶ 30 s", "ghost", "Previsualizar 30 segundos con la voz clonada"
        )
        self.btn_preview.setFixedHeight(34)
        self.btn_pilot = self._btn(
            "▶  Narrar", "primary", "Narrar el capítulo seleccionado a MP3"
        )
        self.btn_fx = QToolButton()
        self.btn_fx.setObjectName("fx")
        self.btn_fx.setText("FX")
        self.btn_fx.setFixedHeight(34)
        self.btn_fx.setCursor(Qt.PointingHandCursor)
        self.btn_fx.setToolTip("Efecto de voz para la narración")
        self.btn_fx.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_fx.setMenu(self._build_fx_menu())
        self.btn_regen = self._btn(
            "Regenerar", "accent", "Regenerar solo el fragmento seleccionado"
        )
        self.btn_more = QToolButton()
        self.btn_more.setObjectName("more")
        self.btn_more.setText("⋯")
        self.btn_more.setFixedSize(34, 34)
        self.btn_more.setCursor(Qt.PointingHandCursor)
        self.btn_more.setToolTip("Más acciones")
        self.btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_more.setMenu(self._build_menu())
        for widget in (
            self.btn_preview, self.btn_pilot, self.btn_fx,
            self.btn_regen, self.btn_more,
        ):
            actions.addWidget(widget)
        bottom.addLayout(actions)
        lay.addLayout(bottom)
        return card

    def _build_fx_menu(self) -> QMenu:
        menu = QMenu(self)
        self.fx_actions = {}
        for key in [""] + sorted(PRESETS):
            label = "Sin efecto" if not key else key.replace("_", " ").capitalize()
            action = menu.addAction(label)
            action.setCheckable(True)
            if key:
                action.setToolTip(PRESETS[key].description)
            action.triggered.connect(
                lambda _checked=False, selected=key: self._set_fx(selected)
            )
            self.fx_actions[key] = action
        self.fx_actions[""].setChecked(True)
        return menu

    def _set_fx(self, key: str) -> None:
        self.fx_preset = key or ""
        for preset, action in self.fx_actions.items():
            action.setChecked(preset == self.fx_preset)
        if not self.fx_preset:
            self.btn_fx.setText("FX")
            self.btn_fx.setToolTip("Efecto de voz: sin efecto")
        else:
            label = self.fx_preset.replace("_", " ").capitalize()
            self.btn_fx.setText(f"FX · {label}")
            self.btn_fx.setToolTip(f"Efecto: {PRESETS[self.fx_preset].description}")

    def _fx_args(self) -> list[str]:
        return ["--fx", self.fx_preset] if self.fx_preset else []

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Refrescar", self.refresh_all)
        menu.addAction("Abrir carpeta de exportaciones", self.action_open_exports)
        menu.addAction("Gestionar voces…", self.action_manage_voices)
        menu.addAction("Editar capítulo…", self.action_edit_chapter)
        menu.addSeparator()
        self.act_preview = menu.addAction("Previsualizar 30 s…", self.action_preview_30)
        self.act_wav = menu.addAction("Preparar WAV maestro…", self.action_wav)
        self.act_mp3 = menu.addAction("Convertir a MP3…", self.action_mp3)
        menu.addSeparator()
        self.act_cancel = menu.addAction("Cancelar trabajo", self.action_cancel)
        self.act_cleanup = menu.addAction("Limpiar trabajos terminados", self.action_cleanup)
        menu.addSeparator()
        # Selector de tema
        theme_menu = menu.addMenu("Tema")
        for theme_name in ("night_city", "nova"):
            action = theme_menu.addAction(theme_name.replace("_", " ").title())
            action.setCheckable(True)
            action.setChecked(theme_name == self._current_theme)
            action.triggered.connect(lambda _, t=theme_name: self.apply_theme(t))
        menu.addSeparator()
        self.act_delete = menu.addAction("Borrar proyecto…", self.action_delete_project)
        return menu

    def apply_theme(self, theme_name: str) -> None:
        """Cambia el tema de la aplicación en runtime y persiste la elección."""
        from voxforge.ui.theme import apply_theme as _apply_theme, PALETTES
        if theme_name not in PALETTES:
            return
        _apply_theme(QApplication.instance(), theme_name)
        self._current_theme = theme_name
        try:
            setattr(self.settings, "theme", theme_name)
        except Exception:
            pass
        # Forzar actualización del menú de tema
        self.menu().update()

    # ------------------------------------------------------------------ #
    # Contenido principal                                                 #
    # ------------------------------------------------------------------ #

    def _build_welcome(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addStretch(1)

        hero = QFrame()
        hero.setObjectName("welcomeHero")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(30, 26, 30, 26)
        hl.setSpacing(9)

        eyebrow = QLabel("EMPIEZA AQUÍ")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Tu próximo audiolibro empieza aquí")
        title.setObjectName("welcomeTitle")
        subtitle = QLabel(
            "Importa un libro y VoxForge lo convierte en capítulos narrados "
            "con tu propia voz, sin salir de tu equipo."
        )
        subtitle.setObjectName("welcomeSub")
        subtitle.setWordWrap(True)
        hl.addWidget(eyebrow)
        hl.addWidget(title)
        hl.addWidget(subtitle)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_welcome_import = self._btn(
            "＋  Importar libro", "primary", "Crear un proyecto a partir de un libro"
        )
        self.btn_welcome_import.setMinimumHeight(38)
        self.btn_welcome_import.clicked.connect(self.action_import_book)
        actions.addWidget(self.btn_welcome_import)
        actions.addStretch(1)
        hl.addLayout(actions)

        trust = QLabel("100 % local  ·  sin conexión  ·  tus voces se quedan en tu equipo")
        trust.setObjectName("welcomeTrust")
        hl.addWidget(trust)
        lay.addWidget(hero)

        steps = QHBoxLayout()
        steps.setSpacing(10)
        step_data = (
            ("01", "Importa un libro", "TXT, DOCX, EPUB o PDF. OCR automático."),
            ("02", "Elige un capítulo", "Revisa los fragmentos y decide qué narrar."),
            ("03", "Narra y exporta", "MP3, WAV o FLAC con la voz que elijas."),
        )
        for number, step_title, step_text in step_data:
            card = QFrame()
            card.setObjectName("stepCard")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(3)
            num = QLabel(number)
            num.setObjectName("stepNumber")
            st = QLabel(step_title)
            st.setObjectName("stepTitle")
            tx = QLabel(step_text)
            tx.setObjectName("stepText")
            tx.setWordWrap(True)
            cl.addWidget(num)
            cl.addWidget(st)
            cl.addWidget(tx)
            steps.addWidget(card, 1)
        lay.addLayout(steps)
        lay.addStretch(1)
        return page

    def _build_content(self) -> QSplitter:
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(10)
        split.addWidget(self._build_fragments_card())
        split.addWidget(self._build_tabs())
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        return split

    def _build_fragments_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("FRAGMENTOS")
        title.setObjectName("cardTitle")
        self.lbl_frag_count = QLabel("—")
        self.lbl_frag_count.setObjectName("count")
        head.addWidget(title)
        head.addWidget(self.lbl_frag_count)
        head.addStretch(1)
        self.frag_search = QLineEdit()
        self.frag_search.setObjectName("search")
        self.frag_search.setPlaceholderText("Buscar en el capítulo…")
        self.frag_search.setClearButtonEnabled(True)
        self.frag_search.setMinimumWidth(100)
        self.frag_search.setMaximumWidth(200)
        self.btn_reload = self._btn(
            "↻", "icon", "Volver a trocear el capítulo (tras editar el diccionario)"
        )
        self.btn_reload.setFixedSize(30, 30)
        head.addWidget(self.frag_search)
        head.addWidget(self.btn_reload)
        lay.addLayout(head)

        self.fragments = EmptyList(
            "Selecciona un capítulo para ver sus fragmentos.\n"
            "Cada tarjeta es un bloque de texto que se narra de una vez."
        )
        self.fragments.setItemDelegate(CardDelegate(height=56, parent=self.fragments))
        self.fragments.setSpacing(4)
        self.fragments.setAlternatingRowColors(True)
        lay.addWidget(self.fragments, 1)
        return card

    def _build_tabs(self) -> QTabWidget:
        self.tabs = QTabWidget()
        self.tabs.setObjectName("tabs")
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tabs.addTab(self._build_jobs_page(), "Trabajos")
        self.tabs.addTab(self._build_exports_page(), "Exportaciones")
        return self.tabs

    def _build_jobs_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("TRABAJOS")
        title.setObjectName("cardTitle")
        self.lbl_job_count = QLabel("0")
        self.lbl_job_count.setObjectName("count")
        head.addWidget(title)
        head.addWidget(self.lbl_job_count)
        head.addStretch(1)
        lay.addLayout(head)

        self.jobs = EmptyList(
            "Sin trabajos todavía.\nLanza una narración para ver aquí el progreso."
        )
        self.jobs.setItemDelegate(CardDelegate(height=56, parent=self.jobs))
        self.jobs.setSpacing(4)
        self.jobs.setAlternatingRowColors(True)
        self.jobs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.jobs.setMinimumHeight(80)
        lay.addWidget(self.jobs, 1)

        progress = QFrame()
        progress.setObjectName("progressCard")
        progress.setMinimumHeight(88)
        pf = QVBoxLayout(progress)
        pf.setContentsMargins(12, 10, 12, 10)
        pf.setSpacing(6)
        phead = QHBoxLayout()
        phead.setSpacing(8)
        self.prog_title = QLabel("Sin trabajo activo")
        self.prog_title.setObjectName("progTitle")
        self.prog_title.setWordWrap(True)
        self.prog_pct = QLabel("0 %")
        self.prog_pct.setObjectName("chipAccent")
        phead.addWidget(self.prog_title)
        phead.addStretch(1)
        phead.addWidget(self.prog_pct)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.prog_text = QLabel("Selecciona un trabajo para ver su registro.")
        self.prog_text.setObjectName("progText")
        self.prog_text.setWordWrap(True)
        self.prog_meta = QLabel("")
        self.prog_meta.setObjectName("progMeta")
        self.prog_meta.setWordWrap(True)
        self.prog_eta = QLabel("")
        self.prog_eta.setObjectName("chipAccent")
        self.prog_eta.setWordWrap(True)
        self.prog_eta.setVisible(False)
        prog_row = QHBoxLayout()
        prog_row.setSpacing(8)
        prog_row.addWidget(self.prog_text, 1)
        prog_row.addWidget(self.prog_eta)
        pf.addLayout(phead)
        pf.addWidget(self.progress)
        
        # Barra de progreso con ETA (tiempo restante)
        eta_row = QHBoxLayout()
        eta_row.setSpacing(8)
        eta_label = QLabel("ETA restante")
        eta_label.setObjectName("hint")
        eta_label.setStyleSheet("color: #6f82a2; font-size: 9px;")
        self.eta_bar = QProgressBar()
        self.eta_bar.setObjectName("etaBar")
        self.eta_bar.setRange(0, 100)
        self.eta_bar.setValue(0)
        self.eta_bar.setTextVisible(False)
        self.eta_bar.setMaximumHeight(10)
        eta_row.addWidget(eta_label)
        eta_row.addWidget(self.eta_bar, 1)
        pf.addLayout(eta_row)
        pf.addLayout(prog_row)
        pf.addWidget(self.prog_meta)
        lay.addWidget(progress)

        log_title = QLabel("REGISTRO")
        log_title.setObjectName("section")
        lay.addWidget(log_title)
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.log.setMaximumBlockCount(2000)
        self.log.setPlaceholderText("El registro del trabajo aparecerá aquí…")
        lay.addWidget(self.log, 2)
        return page

    def _build_exports_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("EXPORTACIONES")
        title.setObjectName("cardTitle")
        self.lbl_exp_count = QLabel("0")
        self.lbl_exp_count.setObjectName("count")
        head.addWidget(title)
        head.addWidget(self.lbl_exp_count)
        head.addStretch(1)
        self.chk_all = QCheckBox("Todas")
        self.chk_all.setToolTip("Mostrar las exportaciones de todo el proyecto")
        self.btn_open = self._btn("↗", "icon", "Abrir la carpeta de exportaciones")
        self.btn_open.setFixedSize(30, 30)
        head.addWidget(self.chk_all)
        head.addWidget(self.btn_open)
        lay.addLayout(head)

        self.exports = EmptyList(
            "Sin exportaciones todavía.\nGenera un piloto o un máster para verlo aquí."
        )
        self.exports.setItemDelegate(CardDelegate(height=54, parent=self.exports))
        self.exports.setSpacing(4)
        self.exports.setAlternatingRowColors(True)
        self.exports.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.exports.setMinimumHeight(80)
        lay.addWidget(self.exports, 1)

        hint = QLabel("Doble clic para reproducir")
        hint.setObjectName("count")
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.exp_hint = hint
        lay.addWidget(hint)
        return page

    # ------------------------------------------------------------------ #
    # Reproductor                                                         #
    # ------------------------------------------------------------------ #

    def _build_player_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("playerBar")
        bar.setMinimumHeight(60)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        self.player_art = QLabel("V")
        self.player_art.setObjectName("art")
        self.player_art.setFixedSize(42, 42)
        self.player_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.player_art)

        info = QVBoxLayout()
        info.setSpacing(1)
        self.player_file = QLabel("Sin reproducción")
        self.player_file.setObjectName("playerFile")
        self.player_sub = QLabel("Doble clic en una exportación")
        self.player_sub.setObjectName("playerSub")
        info.addWidget(self.player_file)
        info.addWidget(self.player_sub)
        lay.addLayout(info, 1)

        self.btn_play = self._btn("▶", "play", "Reproducir / pausar")
        self.btn_play.setFixedSize(40, 40)
        self.btn_stop = self._btn("■", "icon", "Detener")
        self.btn_stop.setFixedSize(32, 32)
        lay.addWidget(self.btn_play)
        lay.addWidget(self.btn_stop)

        center = QVBoxLayout()
        center.setSpacing(2)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setEnabled(False)
        times = QHBoxLayout()
        times.setSpacing(4)
        self.pos_label = QLabel("0:00")
        self.pos_label.setObjectName("time")
        slash = QLabel("/")
        slash.setObjectName("time")
        self.dur_label = QLabel("0:00")
        self.dur_label.setObjectName("time")
        times.addWidget(self.pos_label)
        times.addWidget(slash)
        times.addWidget(self.dur_label)
        times.addStretch(1)
        center.addWidget(self.seek_slider)
        center.addLayout(times)
        lay.addLayout(center, 3)

        vol = QHBoxLayout()
        vol.setSpacing(6)
        vol_label = QLabel("VOL")
        vol_label.setObjectName("count")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.vol_slider.setMinimumWidth(60)
        self.vol_value = QLabel("80 %")
        self.vol_value.setObjectName("time")
        vol.addWidget(vol_label)
        vol.addWidget(self.vol_slider, 1)
        vol.addWidget(self.vol_value)
        lay.addLayout(vol)
        return bar

    # ------------------------------------------------------------------ #
    # Señales y atajos                                                    #
    # ------------------------------------------------------------------ #

    def _wire_signals(self) -> None:
        self.projects.currentItemChanged.connect(self.on_project_changed)
        self.chapters.currentItemChanged.connect(self.on_chapter_changed)
        self.fragments.currentItemChanged.connect(self.on_fragment_changed)
        self.jobs.currentItemChanged.connect(self.on_job_changed)
        self.exports.itemDoubleClicked.connect(self.on_export_double_clicked)
        self.chapters.itemDoubleClicked.connect(self.action_edit_chapter)

        self.frag_search.textChanged.connect(self._render_fragments)
        self.chk_all.toggled.connect(self._on_toggle_exports)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.btn_import.clicked.connect(self.action_import_book)
        self.btn_pilot.clicked.connect(self.action_pilot)
        self.btn_preview.clicked.connect(self.action_preview_30)
        self.btn_regen.clicked.connect(self.action_regen_fragment)
        self.btn_reload.clicked.connect(self.action_load_fragments)
        self.btn_refresh.clicked.connect(self.refresh_all)
        self.btn_open.clicked.connect(self.action_open_exports)
        self.btn_voices.clicked.connect(self.action_manage_voices)
        self.btn_edit_chapter.clicked.connect(self.action_edit_chapter)

        self.btn_play.clicked.connect(self.player_toggle)
        self.btn_stop.clicked.connect(self.player_stop)
        self.vol_slider.valueChanged.connect(self.player_set_volume)
        self.seek_slider.sliderPressed.connect(self._seek_pressed)
        self.seek_slider.sliderMoved.connect(self._seek_moved)
        self.seek_slider.sliderReleased.connect(self._seek_released)

    def _build_shortcuts(self) -> None:
        self._shortcuts: list[QShortcut] = []
        for sequence, handler in (
            ("Ctrl+F", self._focus_search),
            ("Ctrl+R", self.refresh_all),
            ("Ctrl+E", self.action_edit_chapter),
            ("Space", self._space_toggle),
            ("Escape", self._clear_search),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    def _focus_search(self) -> None:
        if self.frag_search.isEnabled():
            self.frag_search.setFocus()
            self.frag_search.selectAll()

    def _clear_search(self) -> None:
        if self.frag_search.text():
            self.frag_search.clear()

    def _space_toggle(self) -> None:
        focused = QApplication.focusWidget()
        if isinstance(focused, QAbstractButton):
            focused.click()
            return
        if isinstance(focused, (QLineEdit, QPlainTextEdit, QTextEdit)):
            return
        self.player_toggle()

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self.refresh_exports()
        else:
            self.refresh_jobs()

    def _build_player(self) -> None:
        self.player = None
        self._seeking = False
        if not HAS_MULTIMEDIA:
            self.player_file.setText("QtMultimedia no disponible")
            self.player_sub.setText("La reproducción no está disponible")
            self.btn_play.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.seek_slider.setEnabled(False)
            self.vol_slider.setEnabled(False)
            return

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state)
        self.player.errorOccurred.connect(self._on_player_error)
        self.btn_play.setEnabled(False)
        self.btn_stop.setEnabled(False)

    # ------------------------------------------------------------------ #
    # Animaciones / progreso                                              #
    # ------------------------------------------------------------------ #

    def _tick(self) -> None:
        self.refresh_jobs()
        self.refresh_selected_log()
        self.refresh_status()
        self._adjust_timers()

    def _adjust_timers(self) -> None:
        try:
            active = self.job_store.active_jobs()
        except Exception:
            active = []
        self._running = bool(active)

        # tail_timer: más frecuente si hay trabajo, detenido si está totalmente inactivo
        if self._running:
            self.tail_timer.setInterval(REFRESH_RUNNING_MS)
            if not self.tail_timer.isActive():
                self.tail_timer.start()
        else:
            self.tail_timer.setInterval(REFRESH_IDLE_MS * 4)
            if not self.tail_timer.isActive():
                self.tail_timer.start()

        # _eta_timer: solo cuando hay un trabajo seleccionado y en curso
        want_eta = self.selected_job_id is not None and self._job_start_time is not None and self._running
        if want_eta and not self._eta_timer.isActive():
            self._eta_timer.start()
        elif not want_eta and self._eta_timer.isActive():
            self._eta_timer.stop()

        # fx_timer: solo animar si hay trabajo activo y animaciones habilitadas
        want_fx = ENABLE_ANIM and self._running
        if want_fx and not self.fx_timer.isActive():
            self.fx_timer.start()
        elif not want_fx and self.fx_timer.isActive():
            self.fx_timer.stop()

    def _fx_tick(self) -> None:
        if not ENABLE_ANIM:
            return
        # marquee cuando el progreso es indeterminado
        if getattr(self, "_prog_indeterminate", False):
            self._marquee_val += self._marquee_dir * 4
            if self._marquee_val >= 100:
                self._marquee_val = 100
                self._marquee_dir = -1
            elif self._marquee_val <= 0:
                self._marquee_val = 0
                self._marquee_dir = 1
            self.progress.setValue(self._marquee_val)
        # shimmer del texto de progreso
        self._shimmer = (self._shimmer + 1) % 4
        dots = "." * self._shimmer
        base = getattr(self, "_prog_base_text", "")
        if base:
            self.prog_text.setText(base + " " + dots)

    def _tick_eta(self) -> None:
        """Actualiza la barra de ETA con el tiempo restante estimado."""
        if self.selected_job_id is None or self._job_start_time is None:
            self.eta_bar.setValue(0)
            return
        try:
            job = self.job_store.get_job(self.selected_job_id)
        except Exception:
            return
        if job is None or job.get("status") == "succeeded":
            self.eta_bar.setValue(100)
            return
        prog = self._compute_progress(job, "")
        if prog["done"] or prog["indeterminate"] or prog["value"] < 3:
            self.eta_bar.setValue(0)
            return
        elapsed = time.time() - self._job_start_time
        eta_s = elapsed * (100 - prog["value"]) / prog["value"]
        if eta_s <= 0:
            self.eta_bar.setValue(100)
        else:
            # Barra de ETA: muestra cuánto QUEDA (100 = todo el tiempo restante)
            self.eta_bar.setValue(min(100, int(eta_s / max(elapsed, 1) * 100)))

    def _animate_progress_to(self, target: int) -> None:
        """Anima la barra de progreso principal hacia el valor objetivo."""
        current = self.progress.value()
        if current == target:
            return
        self._prog_anim = QPropertyAnimation(self.progress, b"value")
        self._prog_anim.setDuration(300)
        self._prog_anim.setStartValue(current)
        self._prog_anim.setEndValue(target)
        self._prog_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._prog_anim.start()

    # ------------------------------------------------------------------ #
    # Cálculo de progreso                                                  #
    # ------------------------------------------------------------------ #

    def _compute_progress(self, job, log_text: str) -> dict:
        out = {"indeterminate": False, "value": 0, "title": "SIN TRABAJO ACTIVO",
               "text": "", "done": False, "failed": False}
        if job is None:
            return out

        status = job.get("status")
        out["title"] = f"#{job['id']} · {job.get('name') or job.get('kind') or '-'}"
        if status in ("succeeded", "failed", "canceled", "lost"):
            out["done"] = True
            out["failed"] = status in ("failed", "lost")
            out["indeterminate"] = False
            out["value"] = 100 if status == "succeeded" else 0
            out["text"] = {"succeeded": "Completado", "failed": "Fallido",
                           "canceled": "Cancelado", "lost": "Perdido"}.get(status, status)
            return out

        # inferir tipo desde el comando guardado
        import json
        try:
            cmd = json.loads(job.get("command") or "[]")
        except Exception:
            cmd = []
        cmd_str = " ".join(str(x) for x in cmd).lower()

        # OCR de un PDF escaneado: es la fase más larga de una importación.
        ocr = re.findall(r"OCR\s+(\d+)/(\d+)\s+páginas", log_text)
        if ocr:
            c, t = ocr[-1]
            try:
                value = int(int(c) / max(int(t), 1) * 100)
            except Exception:
                value = 0
            out["value"] = max(0, min(99, value))
            out["text"] = f"OCR {c}/{t} páginas"
            return out

        if "project-narrate" in cmd_str:
            total_caps = 0
            if job.get("project"):
                try:
                    total_caps = len(list_chapters(self.db_path, job["project"]))
                except Exception:
                    total_caps = 0
            started = len(re.findall(r"===\s*Capítulo", log_text))
            frags = re.findall(r"\[(\d+)/(\d+)\]", log_text)
            frac = 0.0
            if frags:
                c, t = frags[-1]
                try:
                    frac = int(c) / int(t)
                except Exception:
                    frac = 0.0
            if total_caps > 0:
                val = int(((max(started - 1, 0) + frac) / total_caps) * 100)
                out["value"] = max(0, min(100, val))
                out["text"] = f"Capítulo {started}/{total_caps} · frag {frags[-1][0] if frags else 0}/{frags[-1][1] if frags else '?'}"
            else:
                out["indeterminate"] = True
                out["text"] = f"Capítulo {started}" + (f" · frag {frags[-1][0]}/{frags[-1][1]}" if frags else "")
            return out

        if "chapter" in cmd_str and ("narrate" in cmd_str or "regen" in cmd_str):
            frags = re.findall(r"\[(\d+)/(\d+)\]", log_text)
            if frags:
                c, t = frags[-1]
                try:
                    out["value"] = int(int(c) / int(t) * 100)
                    out["text"] = f"Fragmento {c}/{t}"
                except Exception:
                    out["indeterminate"] = True
            else:
                out["indeterminate"] = True
                out["text"] = "Cargando modelo…"
            return out

        if "fx" in cmd_str and "batch" in cmd_str:
            ok = len(re.findall(r"^OK:", log_text, re.M))
            tot = re.search(r"Procesados:\s*(\d+)", log_text)
            if tot:
                out["value"] = 100
                out["text"] = f"{tot.group(1)} archivos"
            else:
                out["indeterminate"] = True
                out["text"] = f"{ok} archivos procesados"
            return out

        if "project" in cmd_str and "import" in cmd_str:
            caps = len(re.findall(r"capítulo\s+\d+", log_text))
            tot = re.search(r"Total:\s*(\d+)\s*partes", log_text)
            if tot:
                out["value"] = 100
                out["text"] = f"{tot.group(1)} partes"
            else:
                out["indeterminate"] = True
                out["text"] = f"{caps} capítulos añadidos" if caps else "Preparando capítulos…"
            return out

        # genérico: buscar [i/total]
        frags = re.findall(r"\[(\d+)/(\d+)\]", log_text)
        if frags:
            c, t = frags[-1]
            try:
                out["value"] = int(int(c) / int(t) * 100)
                out["text"] = f"{c}/{t}"
            except Exception:
                out["indeterminate"] = True
        else:
            out["indeterminate"] = True
            out["text"] = "En ejecución…"
        return out

    # ------------------------------------------------------------------ #
    # Reproductor                                                         #
    # ------------------------------------------------------------------ #

    def _on_position_changed(self, ms: int) -> None:
        self.pos_label.setText(_fmt_ms(ms))
        if not self._seeking:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(max(0, ms))
            self.seek_slider.blockSignals(False)

    def _on_duration_changed(self, ms: int) -> None:
        ms = max(0, ms)
        self.seek_slider.blockSignals(True)
        self.seek_slider.setRange(0, ms)
        self.seek_slider.blockSignals(False)
        self.dur_label.setText(_fmt_ms(ms))
        self.seek_slider.setEnabled(ms > 0)
        self.btn_stop.setEnabled(ms > 0)

    def _on_playback_state(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.btn_play.setText("❚❚" if playing else "▶")

    def _on_player_error(self, error, error_string: str) -> None:
        name = getattr(error, "name", str(error))
        self.log.appendPlainText(f"[player] ERROR {name}: {error_string}")
        self._toast("No se pudo reproducir el archivo.")

    def _set_now_playing(self, path) -> None:
        self.now_playing = path
        if path:
            self.player_file.setText(path.name)
            self.player_file.setToolTip(str(path))
            try:
                stat = path.stat()
                kind = path.suffix.lstrip(".").upper() or "AUDIO"
                self.player_sub.setText(
                    f"{_fmt_size(stat.st_size)}  ·  {kind}  ·  {_fmt_ago(stat.st_mtime)}"
                )
                self.player_art.setText(kind[:3])
            except OSError:
                self.player_sub.setText("Archivo no disponible")
                self.player_art.setText("V")
            self.seek_slider.setEnabled(True)
            self.btn_play.setEnabled(True)
            self.btn_stop.setEnabled(True)
        else:
            self.player_file.setText("Sin reproducción")
            self.player_file.setToolTip("")
            self.player_sub.setText("Doble clic en una exportación")
            self.player_art.setText("V")
            self.seek_slider.setEnabled(False)
            self.btn_play.setEnabled(False)
            self.btn_stop.setEnabled(False)
        self._decorate_exports()

    def _decorate_exports(self) -> None:
        for i in range(self.exports.count()):
            it = self.exports.item(i)
            raw = it.data(ROLE_ID)
            if not raw:
                continue
            path = Path(raw)
            active = bool(self.now_playing and path == self.now_playing)
            it.setData(ROLE_BADGE, "▶" if active else path.suffix.lstrip(".").upper())
            it.setData(ROLE_BADGE_COLOR, CYAN if active else MUTED)
            it.setData(ROLE_ACCENT, CYAN if active else None)
        self.exports.viewport().update()

    def player_toggle(self) -> None:
        if self.player is None:
            self._toast("QtMultimedia no está disponible.")
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            return
        if self.player.source().isEmpty():
            self._toast("Doble clic en una exportación para escucharla.")
            return
        self.player.play()
        self._set_now_playing(Path(self.player.source().toLocalFile()))

    def player_play(self) -> None:
        if self.player is None:
            self._toast("QtMultimedia no está disponible.")
            return
        if self.player.source().isEmpty():
            self._toast("Doble clic en una exportación para escucharla.")
            return
        self.player.play()
        self._set_now_playing(Path(self.player.source().toLocalFile()))

    def player_pause(self) -> None:
        if self.player:
            self.player.pause()

    def player_stop(self) -> None:
        if not self.player:
            return
        self.player.stop()
        self.player.setPosition(0)
        self.seek_slider.blockSignals(True)
        self.seek_slider.setValue(0)
        self.seek_slider.blockSignals(False)
        self.pos_label.setText("0:00")
        self.btn_play.setText("▶")

    def player_set_volume(self, value: int) -> None:
        if getattr(self, "audio_output", None):
            self.audio_output.setVolume(value / 100.0)
        if hasattr(self, "vol_value"):
            self.vol_value.setText(f"{value} %")

    def _seek_pressed(self) -> None:
        self._seeking = True

    def _seek_moved(self, value: int) -> None:
        self.pos_label.setText(_fmt_ms(value))

    def _seek_released(self) -> None:
        self._seeking = False
        if self.player and self.seek_slider.isEnabled():
            self.player.setPosition(self.seek_slider.value())

    def on_export_double_clicked(self, item: QListWidgetItem) -> None:
        if self.player is None:
            self._toast("QtMultimedia no está disponible.")
            return
        path = item.data(ROLE_ID)
        if not path:
            return
        p = Path(path)
        if not p.is_file():
            self._toast(f"No existe:\n{p}")
            return
        self.player.setSource(QUrl.fromLocalFile(str(p)))
        self.player.play()
        self._set_now_playing(p)

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _toast(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 7000)
        self.log.appendPlainText(f"» {msg}")

    def _selected_item_data(self, widget: QListWidget):
        item = widget.currentItem()
        return item.data(ROLE_ID) if item is not None else None

    def _require_project(self):
        if not self.current_project:
            self._toast("Selecciona un proyecto en la barra lateral.")
            return None
        return self.current_project

    def _require_chapter(self):
        if self._require_project() is None:
            return None
        if self.current_chapter is None:
            self._toast("Selecciona un capítulo en la barra lateral.")
            return None
        return int(self.current_chapter)

    def _clear_fragments(self) -> None:
        self.fragments.blockSignals(True)
        self.fragments.clear()
        self.fragments.blockSignals(False)
        self._fragment_entries = []
        self._frag_stats = (0, 0)
        self._frag_key = None
        self.selected_fragment = None
        if hasattr(self, "lbl_frag_count"):
            self.lbl_frag_count.setText("—")

    @staticmethod
    def _list_height(count: int, maximum: int = 170) -> int:
        """Altura compacta para las listas de la barra lateral."""
        if count <= 0:
            return 96
        return min(maximum, count * 56 + 4)

    def _exports_dir(self) -> Path:
        base = self.data_dir / "exports"
        return base / self.current_project if self.current_project else base

    # ------------------------------------------------------------------ #
    # Refresco                                                            #
    # ------------------------------------------------------------------ #

    def refresh_all(self) -> None:
        self.refresh_status()
        self.refresh_projects()
        self.refresh_jobs()
        self.refresh_selected_log()
        self._update_context()
        self._update_actions()

    def refresh_status(self) -> None:
        try:
            store = Store(self.db_path)
            try:
                voices = store.list_profiles()
                frags = store.fragment_count()
            finally:
                store.close()
            self.badge_voices.setText(_plural(len(voices), "voz", "voces"))
            self.badge_cache.setText(f"{frags} en caché")
            names = ", ".join(p["name"] for p in voices[:4])
            self.badge_voices.setToolTip(f"Perfiles: {names}" if names else "Sin perfiles")
            cls, txt = _cpu_class(cpu_temp_c())
            if self.badge_cpu.objectName() != cls:
                self.badge_cpu.setObjectName(cls)
                self.badge_cpu.style().unpolish(self.badge_cpu)
                self.badge_cpu.style().polish(self.badge_cpu)
            self.badge_cpu.setText(txt)
        except Exception as exc:
            self.badge_cpu.setText(f"error: {exc}")

    def refresh_projects(self) -> None:
        old = self.current_project
        self.projects.blockSignals(True)
        self.projects.clear()
        try:
            projects = list_projects(self.db_path)
        except Exception as exc:
            self.projects.blockSignals(False)
            self._toast(f"Proyectos: {exc}")
            return

        self._projects = {p["name"]: p for p in projects}
        row = 0
        for i, p in enumerate(projects):
            it = QListWidgetItem()
            it.setData(ROLE_ID, p["name"])
            it.setData(ROLE_TITLE, p["name"])
            it.setData(ROLE_SUB, f"{p['voice_profile']} · {p['chapters']} capítulos")
            it.setData(ROLE_ACCENT, CYAN if old and p["name"] == old else None)
            self.projects.addItem(it)
            if old and p["name"] == old:
                row = i

        self.lbl_proj_count.setText(str(len(projects)))
        if projects:
            self.projects.setCurrentRow(row)
            self.current_project = self.projects.currentItem().data(ROLE_ID)
        else:
            self.current_project = None
            self.current_chapter = None
            self.chapters.clear()
            self._clear_fragments()
            self.exports.clear()
            self.lbl_exp_count.setText("0")
            if hasattr(self, "exp_hint"):
                self.exp_hint.setVisible(False)
        self.projects.blockSignals(False)
        self.refresh_chapters()
        if hasattr(self, "content_stack"):
            page = self.workspace if self.current_project else self.welcome_page
            self.content_stack.setCurrentWidget(page)
            self.guide_card.setVisible(True)
        self._update_context()
        self._update_actions()

    def refresh_chapters(self) -> None:
        old = self.current_chapter
        self.chapters.blockSignals(True)
        self.chapters.clear()
        self._chapters = {}
        self.lbl_chap_count.setText("0")

        if not self.current_project:
            self.current_chapter = None
            self.chapters.blockSignals(False)
            self._clear_fragments()
            self.exports.clear()
            self.lbl_exp_count.setText("0")
            self.exp_hint.setVisible(False)
            self._update_context()
            self._update_actions()
            return

        try:
            chapters = list_chapters(self.db_path, self.current_project)
        except Exception as exc:
            self.chapters.blockSignals(False)
            self._toast(f"Capítulos: {exc}")
            return

        row = 0
        for i, ch in enumerate(chapters):
            it = QListWidgetItem()
            it.setData(ROLE_ID, ch["ordinal"])
            it.setData(ROLE_NUMBER, f"{ch['ordinal']:02d}")
            it.setData(ROLE_TITLE, ch["title"])
            it.setData(ROLE_SUB, f"{_fmt_int(ch['chars'])} car. · {_fmt_char_minutes(ch['chars'])}")
            it.setToolTip(f"Capítulo {ch['ordinal']} · {ch['title']}")
            self.chapters.addItem(it)
            self._chapters[ch["ordinal"]] = ch
            if old is not None and ch["ordinal"] == old:
                row = i

        self.lbl_chap_count.setText(str(len(chapters)))
        if chapters:
            self.chapters.setCurrentRow(row)
            self.current_chapter = self.chapters.currentItem().data(ROLE_ID)
        else:
            self.current_chapter = None
            self._clear_fragments()
            self.exports.clear()
            self.lbl_exp_count.setText("0")
        self.chapters.blockSignals(False)
        self._auto_load_chapter()
        self._update_context()
        self._update_actions()

    def refresh_jobs(self) -> None:
        prev = self.selected_job_id
        self.jobs.blockSignals(True)
        self.jobs.clear()
        try:
            jobs = self.job_store.list_jobs(limit=100)
        except Exception as exc:
            self.jobs.blockSignals(False)
            self._toast(f"Trabajos: {exc}")
            return

        row = 0
        snapshot: dict[int, str] = {}
        for i, j in enumerate(jobs):
            status = j.get("status") or "pending"
            snapshot[int(j["id"])] = status
            label, color = _status_style(status)
            parts = [f"#{j['id']}"]
            if j.get("project"):
                parts.append(str(j["project"]))
            if j.get("ordinal") is not None:
                parts.append(f"cap {j['ordinal']}")
            if j.get("exit_code") is not None and status in ("failed", "canceled", "lost"):
                parts.append(f"salida {j['exit_code']}")
            it = QListWidgetItem()
            it.setData(ROLE_ID, j["id"])
            it.setData(ROLE_TITLE, j.get("name") or j.get("kind") or "Trabajo")
            it.setData(ROLE_SUB, " · ".join(parts))
            it.setData(ROLE_BADGE, label)
            it.setData(ROLE_BADGE_COLOR, color)
            it.setData(ROLE_ACCENT, color if status in ("running", "pending") else None)
            it.setToolTip(f"Trabajo #{j['id']} · {status}")
            self.jobs.addItem(it)
            if prev is not None and j["id"] == prev:
                row = i

        self.lbl_job_count.setText(str(len(jobs)))
        if jobs:
            self.jobs.setCurrentRow(row)
            self.selected_job_id = self.jobs.currentItem().data(ROLE_ID)
        else:
            self.selected_job_id = None
        self.jobs.blockSignals(False)

        finished = {"succeeded", "failed", "canceled", "lost"}
        for jid, info in list(self._preview_jobs.items()):
            status = snapshot.get(jid)
            if status in finished:
                self._preview_jobs.pop(jid, None)
                info["text"].unlink(missing_ok=True)
                if status == "succeeded":
                    QTimer.singleShot(500, lambda p=info["out"]: self._play_preview(p))
                else:
                    self._toast(f"Preview {status}: no se pudo generar el audio.")
        previous = getattr(self, "_job_snapshot", {})
        first_snapshot = not previous
        if not first_snapshot and any(
            s in finished and previous.get(jid) != s for jid, s in snapshot.items()
        ):
            QTimer.singleShot(0, self.refresh_exports)
            QTimer.singleShot(250, self.refresh_projects)
        self._job_snapshot = snapshot
        self._update_actions()

    def refresh_exports(self) -> None:
        self.exports.blockSignals(True)
        self.exports.clear()
        d = self._exports_dir()
        if not d.is_dir():
            self.lbl_exp_count.setText("0")
            self.exp_hint.setVisible(False)
            self.exports.blockSignals(False)
            return

        prefix = (
            f"{self.current_chapter:03d}"
            if (self.current_chapter and not self.show_all_exports)
            else None
        )
        files = [p for p in d.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS]
        if prefix:
            files = [p for p in files if p.name.startswith(prefix)]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        shown = 0
        for p in files[:300]:
            try:
                stat = p.stat()
            except OSError:
                continue
            it = QListWidgetItem()
            it.setData(ROLE_ID, str(p))
            it.setData(ROLE_TITLE, p.name)
            it.setData(ROLE_SUB, f"{_fmt_size(stat.st_size)} · {_fmt_ago(stat.st_mtime)}")
            it.setData(ROLE_BADGE, p.suffix.lstrip(".").upper())
            it.setData(ROLE_BADGE_COLOR, MUTED)
            it.setToolTip(str(p))
            self.exports.addItem(it)
            shown += 1

        self.lbl_exp_count.setText(
            f"{shown} de {len(files)}" if len(files) > 300 else str(len(files))
        )
        self.exp_hint.setVisible(bool(files))
        self.exports.blockSignals(False)
        self._decorate_exports()

    def refresh_selected_log(self) -> None:
        if self.selected_job_id is None:
            self._prog_indeterminate = False
            self._prog_base_text = ""
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.prog_pct.setText("0 %")
            self.prog_title.setText("Sin trabajo activo")
            self.prog_text.setText("Selecciona un trabajo para ver su registro.")
            self.prog_meta.setText("")
            self.prog_eta.setText("")
            self.prog_eta.setVisible(False)
            self._job_start_time = None
            self._eta_timer.stop()
            self.eta_bar.setValue(0)
            if getattr(self, "_last_log_text", "") != "":
                self.log.setPlainText("")
                self._last_log_text = ""
            return

        try:
            job = self.job_store.get_job(self.selected_job_id)
        except Exception as exc:
            self.log.setPlainText(f"Error: {exc}")
            return
        if job is None:
            self.log.setPlainText("El trabajo ya no existe.")
            return

        log_path = Path(job.get("log_path") or "")
        tail_text = ""
        if log_path.is_file():
            try:
                with log_path.open("rb") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    chunk = min(size, 80_000)
                    f.seek(size - chunk)
                    data = f.read(chunk).decode("utf-8", errors="replace")
                lines = data.splitlines(keepends=True)
                if size > chunk and lines:
                    lines = lines[1:]
                tail_text = "".join(lines[-200:])
            except Exception as exc:
                tail_text = f"(error log: {exc})"

        header = (
            f"Trabajo #{job['id']}  ·  {job['status']}  ·  "
            f"salida {job.get('exit_code') if job.get('exit_code') is not None else '-'}\n"
            f"log: {job.get('log_path') or '-'}\n\n"
        )
        full_text = header + (tail_text or "(sin log)")
        if full_text != getattr(self, "_last_log_text", ""):
            scroll = self.log.verticalScrollBar()
            was_at_bottom = scroll.value() >= scroll.maximum() - 4
            self.log.setPlainText(full_text)
            if was_at_bottom:
                scroll.setValue(scroll.maximum())
            self._last_log_text = full_text

        prog = self._compute_progress(job, tail_text)
        elapsed = _job_elapsed(job)
        prog["elapsed_s"] = elapsed
        if prog["done"] or prog["indeterminate"] or prog["value"] < 3:
            prog["eta_s"] = None
        else:
            prog["eta_s"] = elapsed * (100 - prog["value"]) / prog["value"]

        clock = _fmt_clock(elapsed)
        status = job.get("status")
        if prog["done"]:
            if status == "succeeded":
                meta = f"Completado en {_fmt_duration(elapsed)}" if elapsed else "Completado"
            else:
                meta = f"{prog['text']} · duración {_fmt_duration(elapsed)}" if elapsed else prog["text"]
        elif status == "pending":
            meta = "En cola · empezará en cuanto haya un hueco"
        elif prog["indeterminate"]:
            if "Cargando el modelo" in tail_text:
                meta = f"{clock} transcurridos · primera carga del modelo"
            else:
                meta = f"{clock} transcurridos · estimación pendiente"
        elif prog["value"] >= 100:
            meta = f"{clock} transcurridos · finalizando…"
        elif prog.get("eta_s") is not None:
            meta = f"{clock} transcurridos · quedan ≈ {_fmt_duration(prog['eta_s'])}"
        else:
            meta = f"{clock} transcurridos · calculando estimación…"
        self.prog_meta.setText(meta)

        if prog["done"]:
            eta_text = ""
        elif status == "pending":
            eta_text = "En cola"
        elif prog["indeterminate"]:
            eta_text = "—"
        elif prog.get("eta_s") is not None:
            eta_text = f"≈ {_fmt_duration(prog['eta_s'])}"
        else:
            eta_text = "Calculando"
        self.prog_eta.setText(eta_text)
        self.prog_eta.setVisible(bool(eta_text))

        if prog["done"]:
            self.statusBar().showMessage(f"Trabajo #{job['id']} · {prog['text']}", 5000)
        elif status == "pending":
            self.statusBar().showMessage(f"Trabajo #{job['id']} · en cola", 0)
        elif prog["indeterminate"]:
            self.statusBar().showMessage(
                f"Trabajo #{job['id']} · {clock} · sin estimación todavía", 0
            )
        else:
            self.statusBar().showMessage(
                f"Trabajo #{job['id']} · {prog['value']} % · {eta_text} · {clock}", 0
            )

        self._prog_indeterminate = prog["indeterminate"] and not prog["done"]
        self.prog_title.setText(prog["title"])
        self.progress.setRange(0, 100)
        if prog["done"]:
            self._animate_progress_to(prog["value"])
            self.prog_pct.setText(f"{prog['value']} %")
            self.prog_text.setText(prog["text"])
            self._prog_base_text = ""
            self._job_start_time = None
            self._eta_timer.stop()
            self.eta_bar.setValue(100)
        elif prog["indeterminate"]:
            self.progress.setValue(self._marquee_val)
            self.prog_pct.setText("··")
            self._prog_base_text = prog["text"]
            self.prog_text.setText(prog["text"])
            self._job_start_time = None
            self._eta_timer.stop()
            self.eta_bar.setValue(0)
        else:
            self._animate_progress_to(prog["value"])
            self.prog_pct.setText(f"{prog['value']} %")
            self._prog_base_text = ""
            self.prog_text.setText(prog["text"])
            if self._job_start_time is None:
                self._job_start_time = time.time()
            self._eta_timer.start()

    # ------------------------------------------------------------------ #
    # Señales de selección                                                #
    # ------------------------------------------------------------------ #

    def on_project_changed(self, current, _previous=None) -> None:
        if current is None:
            self.current_project = None
            self.current_chapter = None
            self.refresh_chapters()
            self.content_stack.setCurrentWidget(self.welcome_page)
            self.guide_card.setVisible(True)
            self._update_context()
            self._update_actions()
            return
        self.current_project = current.data(ROLE_ID)
        self.refresh_chapters()
        self.content_stack.setCurrentWidget(self.workspace)
        self.guide_card.setVisible(True)
        self.refresh_status()
        self._update_context()
        self._update_actions()

    def on_chapter_changed(self, current, _previous=None) -> None:
        if current is None:
            self.current_chapter = None
            self._clear_fragments()
            self.exports.clear()
            self.lbl_exp_count.setText("0")
            self._update_context()
            self._update_actions()
            return
        self.current_chapter = current.data(ROLE_ID)
        self._auto_load_chapter()
        self._update_context()
        self._update_actions()

    def on_fragment_changed(self, current, _previous=None) -> None:
        data = current.data(ROLE_ID) if current is not None else None
        self.selected_fragment = int(data) if data is not None else None
        self._update_actions()

    def on_job_changed(self, current, _previous=None) -> None:
        self.selected_job_id = current.data(ROLE_ID) if current is not None else None
        self.refresh_selected_log()
        self._update_actions()

    def _on_toggle_exports(self, checked: bool) -> None:
        self.show_all_exports = checked
        self.refresh_exports()

    # ------------------------------------------------------------------ #
    # Contexto y disponibilidad de acciones                               #
    # ------------------------------------------------------------------ #

    def _update_context(self) -> None:
        project = self.current_project
        if not project:
            self.ctx_eyebrow.setText("BIBLIOTECA")
            self.ctx_title.setText("Sin proyecto")
            self.ctx_sub.setText("Importa un libro para empezar · TXT, DOCX, EPUB o PDF")
            for chip in (self.chip_voice, self.chip_chars, self.chip_frags):
                chip.setVisible(False)
            self.setWindowTitle("VoxForge · Estudio de narración local")
            return

        info = getattr(self, "_projects", {}).get(project, {})
        self.ctx_eyebrow.setText("PROYECTO ACTIVO")
        self.ctx_title.setText(project)
        self.ctx_title.setToolTip(project)
        self.setWindowTitle(f"VoxForge · {project}")

        chapter = self.current_chapter
        chapter_info = getattr(self, "_chapters", {}).get(int(chapter)) if chapter else None
        if chapter_info:
            self.ctx_sub.setText(
                f"Capítulo {chapter_info['ordinal']:02d} · {chapter_info['title']}"
            )
            self.ctx_sub.setToolTip(chapter_info["title"])
        elif chapter:
            self.ctx_sub.setText(f"Capítulo {chapter}")
        else:
            self.ctx_sub.setText("Selecciona un capítulo en la barra lateral")

        self.chip_voice.setText(f"voz · {info.get('voice_profile', '—')}")
        chars = chapter_info["chars"] if chapter_info else 0
        self.chip_chars.setText(f"{_fmt_int(chars)} car." if chars else "—")
        text_frags, pauses = getattr(self, "_frag_stats", (0, 0))
        pause_txt = f" · {_plural(pauses, 'pausa', 'pausas')}" if pauses else ""
        self.chip_frags.setText(f"{_plural(text_frags, 'fragmento', 'fragmentos')}{pause_txt}")
        for chip in (self.chip_voice, self.chip_chars, self.chip_frags):
            chip.setVisible(True)

    def _update_actions(self) -> None:
        project = bool(self.current_project)
        chapter = bool(self.current_chapter)
        fragment = self.selected_fragment is not None

        self.btn_pilot.setEnabled(chapter)
        self.btn_preview.setEnabled(chapter)
        self.act_preview.setEnabled(chapter)
        self.act_wav.setEnabled(project)
        self.act_mp3.setEnabled(project)
        self.btn_regen.setEnabled(fragment)
        if fragment:
            self.btn_regen.setText(f"Regenerar #{self.selected_fragment}")
            self.btn_regen.setToolTip(
                f"Regenerar el fragmento {self.selected_fragment} con otra semilla"
            )
        else:
            self.btn_regen.setText("Regenerar")
            self.btn_regen.setToolTip("Regenerar solo el fragmento seleccionado")
        self.btn_reload.setEnabled(chapter)
        self.btn_edit_chapter.setEnabled(chapter)
        self.btn_open.setEnabled(project)
        self.frag_search.setEnabled(chapter)
        self.act_delete.setEnabled(project)

        job = None
        if self.selected_job_id is not None:
            try:
                job = self.job_store.get_job(self.selected_job_id)
            except Exception:
                job = None
        active = bool(job and job.get("status") in ("pending", "running"))
        self.act_cancel.setEnabled(active)
        self.act_cleanup.setEnabled(True)

    # ------------------------------------------------------------------ #
    # Auto-carga                                                          #
    # ------------------------------------------------------------------ #

    def _auto_load_chapter(self) -> None:
        self._load_fragments(quiet=True)
        self.refresh_exports()
        self._preload_pilot()

    def _preload_pilot(self) -> None:
        if self.current_chapter is None or self.player is None:
            return
        if (
            not self.player.source().isEmpty()
            and self.player.playbackState() != QMediaPlayer.PlaybackState.StoppedState
        ):
            return
        prefix = f"{self.current_chapter:03d}"
        d = self._exports_dir()
        if not d.is_dir():
            return
        cands = [
            p for p in d.rglob("*")
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS and p.name.startswith(prefix)
        ]
        pilot = [p for p in cands if "piloto" in p.name]
        pick = None
        if pilot:
            pick = max(pilot, key=lambda p: p.stat().st_mtime)
        elif cands:
            pick = max(cands, key=lambda p: p.stat().st_mtime)
        if pick:
            self.player.setSource(QUrl.fromLocalFile(str(pick)))
            self._set_now_playing(pick)

    # ------------------------------------------------------------------ #
    # Fragmentos                                                          #
    # ------------------------------------------------------------------ #

    def action_load_fragments(self) -> None:
        self._load_fragments(quiet=False)

    def _load_fragments(self, quiet: bool) -> None:
        chapter = self.current_chapter
        project = self.current_project
        if chapter is None or project is None:
            self._clear_fragments()
            self._update_context()
            if not quiet:
                self._toast("Selecciona un proyecto y un capítulo.")
            return
        try:
            ch = get_chapter(self.db_path, project, chapter)
        except (ProjectNotFound, ChapterNotFound) as exc:
            if not quiet:
                self._toast(f"Error de capítulo: {exc}")
            return

        text = ch["text"]
        try:
            pron_cfg = load_pronunciation(self.data_dir / "pronunciation.json", required=False)
            if pron_cfg is not None:
                text = pron_cfg.apply(text, None)
        except PronunciationError as exc:
            if not quiet:
                self._toast(f"Diccionario: {exc}")
            return
        try:
            segments = split_segments(text, self.settings.max_chunk_chars)
        except PauseError as exc:
            if not quiet:
                self._toast(f"Pausas: {exc}")
            return

        entries: list[dict] = []
        text_index = 0
        pause_count = 0
        for seg in segments:
            if seg.kind == "text":
                text_index += 1
                clean = " ".join(seg.text.split())
                entries.append({
                    "kind": "text",
                    "id": text_index,
                    "text": seg.text,
                    "excerpt": clean,
                })
            else:
                pause_count += 1
                entries.append({
                    "kind": "pause",
                    "id": None,
                    "seconds": seg.seconds,
                    "text": "",
                    "excerpt": "",
                })

        key = (project, chapter)
        previous = self.selected_fragment if getattr(self, "_frag_key", None) == key else None
        self._fragment_entries = entries
        self._frag_stats = (text_index, pause_count)
        self._frag_key = key
        self._render_fragments()
        if previous is not None:
            for row in range(self.fragments.count()):
                if self.fragments.item(row).data(ROLE_ID) == previous:
                    self.fragments.setCurrentRow(row)
                    break
        self._update_context()
        self._update_actions()
        if not quiet:
            self._toast(f"Fragmentos recargados: {text_index} de texto, {pause_count} pausas.")

    def _render_fragments(self) -> None:
        entries = getattr(self, "_fragment_entries", [])
        query = self.frag_search.text().strip().casefold() if hasattr(self, "frag_search") else ""
        if query:
            shown = [
                e for e in entries
                if e["kind"] == "text"
                and (query in e["excerpt"].casefold() or query in e["text"].casefold())
            ]
        else:
            shown = entries

        self.fragments.blockSignals(True)
        self.fragments.clear()
        for entry in shown:
            it = QListWidgetItem()
            if entry["kind"] == "text":
                it.setData(ROLE_ID, entry["id"])
                it.setData(ROLE_NUMBER, f"{entry['id']:02d}")
                it.setData(ROLE_TITLE, entry["excerpt"])
                it.setData(ROLE_SUB, _plural(len(entry["text"]), "carácter", "caracteres"))
                it.setToolTip(entry["text"])
            else:
                it.setData(ROLE_ID, None)
                it.setData(ROLE_TITLE, "Pausa explícita")
                it.setData(ROLE_SUB, f"{entry['seconds']:g} s de silencio")
                it.setData(ROLE_BADGE, "PAUSA")
                it.setData(ROLE_BADGE_COLOR, AMBER)
                it.setData(ROLE_ACCENT, AMBER)
                it.setToolTip(f"Silencio de {entry['seconds']:g} s")
            self.fragments.addItem(it)
        self.fragments.blockSignals(False)

        text_total = sum(1 for e in entries if e["kind"] == "text")
        pauses = sum(1 for e in entries if e["kind"] == "pause")
        if query:
            self.lbl_frag_count.setText(f"{len(shown)} de {text_total}")
            self.fragments.placeholder = f"Sin resultados para «{self.frag_search.text().strip()}»."
        else:
            suffix = f" · {_plural(pauses, 'pausa', 'pausas')}" if pauses else ""
            self.lbl_frag_count.setText(f"{_plural(text_total, 'fragmento', 'fragmentos')}{suffix}")
            self.fragments.placeholder = (
                "Selecciona un capítulo para ver sus fragmentos.\n"
                "Cada tarjeta es un bloque de texto que se narra de una vez."
            )
        self.fragments.viewport().update()
        self.selected_fragment = None
        self._update_actions()

    # ------------------------------------------------------------------ #
    # Jobs                                                                #
    # ------------------------------------------------------------------ #

    def _set_busy(self, busy: bool) -> None:
        """Deshabilita/habilita los botones que lanzan QProcess mientras hay
        uno en vuelo, evitando doble clic/reentrancia (CA-3)."""
        if self._busy == busy:
            return
        self._busy = busy
        for widget in (
            getattr(self, "btn_import", None),
            getattr(self, "btn_pilot", None),
            getattr(self, "btn_regen", None),
            getattr(self, "act_wav", None),
            getattr(self, "act_mp3", None),
        ):
            if widget is not None:
                widget.setEnabled(not busy)

    def _run_cli_async(self, cmd: list[str], on_done) -> None:
        """Ejecuta un comando de CLI sin bloquear el event loop (QProcess)."""
        self._set_busy(True)
        proc = QProcess(self)
        proc.setProgram(cmd[0])
        proc.setArguments(cmd[1:])
        proc.setWorkingDirectory(str(ROOT))

        def on_finished(exit_code, _exit_status):
            output = proc.readAllStandardOutput().data().decode(errors="replace")
            err = proc.readAllStandardError().data().decode(errors="replace")
            proc.deleteLater()
            self._procs.discard(proc)
            self._set_busy(False)
            on_done(exit_code, output + err)

        def on_error(error):
            proc.deleteLater()
            self._procs.discard(proc)
            self._set_busy(False)
            on_done(1, f"QProcess error: {error}")

        proc.finished.connect(on_finished)
        proc.errorOccurred.connect(on_error)
        self._procs.add(proc)
        proc.start()

    def start_job(
        self, title, args, project=None, ordinal=None, allow_duplicate=False,
        on_done=None,
    ) -> None:
        cmd = [sys.executable, "-m", "voxforge", "job", "start", "--name", title]
        if project:
            cmd += ["--project", project]
        if ordinal is not None:
            cmd += ["--ordinal", str(ordinal)]
        if allow_duplicate:
            cmd.append("--allow-duplicate")
        cmd += ["--"] + [str(a) for a in args]

        def _on_done(exit_code, output):
            if exit_code != 0:
                self._toast(f"No se pudo lanzar: {output}")
                if on_done:
                    on_done(None)
                return
            self.log.setPlainText(output)
            self._last_log_text = ""
            jid = None
            m = re.search(r"id=(\d+)", output)
            if m:
                jid = int(m.group(1))
                self.refresh_jobs()
                self.jobs.blockSignals(True)
                for i in range(self.jobs.count()):
                    if self.jobs.item(i).data(ROLE_ID) == jid:
                        self.jobs.setCurrentRow(i)
                        self.selected_job_id = jid
                        break
                self.jobs.blockSignals(False)
                self.tabs.setCurrentIndex(0)
                self.refresh_selected_log()
                self._adjust_timers()
                self._toast(f"Trabajo #{jid} en marcha.")
            else:
                self.refresh_jobs()
            if on_done:
                on_done(jid)

        self._run_cli_async(cmd, _on_done)

    def run_simple(self, args, on_done=None) -> None:
        cmd = [sys.executable, "-m", "voxforge"] + [str(a) for a in args]

        def _on_done(exit_code, output):
            self.log.setPlainText(output)
            self._last_log_text = ""
            if exit_code != 0:
                self._toast(f"Código {exit_code}")
            self.refresh_jobs()
            self.refresh_status()
            self.refresh_exports()
            self._update_actions()
            if on_done:
                on_done(exit_code)

        self._run_cli_async(cmd, _on_done)

    # ------------------------------------------------------------------ #
    # Acciones                                                            #
    # ------------------------------------------------------------------ #

    def action_import_book(self) -> None:
        try:
            store = Store(self.db_path)
            try:
                voices = [p["name"] for p in store.list_profiles()]
            finally:
                store.close()
        except Exception as exc:
            self._toast(f"No se pudieron leer las voces: {exc}")
            return
        if not voices:
            QMessageBox.information(
                self,
                "Sin perfiles de voz",
                "Todavía no hay ninguna voz. Crea un perfil antes de importar:\n\n"
                "python -m voxforge voice add NOMBRE muestra.wav",
            )
            return

        default_voice = "yo_limpia" if "yo_limpia" in voices else voices[0]
        dialog = ImportBookDialog(self, voices, default_voice)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.data()
        src = Path(data["path"]) if data["path"] else None
        if src is None or not src.is_file():
            self._toast("No se pudo leer el archivo seleccionado.")
            return

        name = data["name"]
        voice = data["voice"]
        try:
            get_project(self.db_path, name)
            exists = True
        except ProjectNotFound:
            exists = False
        if exists:
            resp = QMessageBox.question(
                self,
                "Proyecto existente",
                f"El proyecto '{name}' ya existe. ¿Reemplazarlo?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        args = [
            "project", "import", name,
            "--file", str(src),
            "--voice", voice,
            "--target-chars", "45000",
            "--hard-max-chars", "60000",
        ]
        if exists:
            args.append("--replace")

        def _on_import_done(jid):
            if jid is None:
                return
            # Muestra el progreso del trabajo aunque el proyecto aún no exista.
            self.content_stack.setCurrentWidget(self.workspace)
            self.tabs.setCurrentIndex(0)
            self.ctx_eyebrow.setText("IMPORTANDO")
            self.ctx_title.setText(name)
            self.ctx_sub.setText(f"{src.name} · preparando capítulos…")
            for chip in (self.chip_voice, self.chip_chars, self.chip_frags):
                chip.setVisible(False)

        self.start_job(f"import_{name}", args, project=name, ordinal=None,
                       on_done=_on_import_done)

    def action_manage_voices(self, _checked=False) -> None:
        if getattr(self, "player", None):
            self.player.stop()
        dialog = VoiceManagerDialog(self, self.db_path, self.data_dir)
        dialog.exec()
        self.refresh_status()
        self.refresh_projects()
        self._update_context()
        self._update_actions()

    def action_edit_chapter(self, _item=None) -> None:
        chapter = self._require_chapter()
        if chapter is None:
            return
        project = self.current_project
        try:
            ch = get_chapter(self.db_path, project, chapter)
        except (ProjectNotFound, ChapterNotFound) as exc:
            self._toast(f"No se pudo abrir el capítulo: {exc}")
            return

        dialog = ChapterEditorDialog(self, project, ch, self.settings)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.data()
        try:
            update_chapter(
                self.db_path,
                project,
                chapter,
                title=data["title"],
                text=data["text"],
            )
        except (ProjectError, ChapterNotFound, ProjectNotFound) as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return

        self.selected_fragment = None
        self._frag_key = None
        self.refresh_chapters()
        self._toast("Capítulo actualizado. Los fragmentos se recalcularán al narrar.")
        if data["narrate"]:
            self.action_pilot()

    def action_preview_30(self, _checked=False) -> None:
        chapter = self._require_chapter()
        if chapter is None:
            return
        project = self.current_project
        try:
            ch = get_chapter(self.db_path, project, chapter)
        except (ProjectNotFound, ChapterNotFound) as exc:
            self._toast(f"No se pudo leer el capítulo: {exc}")
            return

        try:
            segments = split_segments(ch["text"], self.settings.max_chunk_chars)
        except PauseError as exc:
            self._toast(f"Pausas: {exc}")
            return

        parts: list[str] = []
        chars = 0
        for seg in segments:
            if seg.kind == "text":
                if parts and chars >= 320:
                    break
                parts.append(seg.text)
                chars += len(seg.text)
            elif parts:
                parts.append(f"[{seg.name}={seg.seconds:g}s]")
            if chars >= 320:
                break
        preview_text = "\n\n".join(parts).strip()
        if not preview_text:
            self._toast("El capítulo no tiene texto para previsualizar.")
            return

        info = self._projects.get(project, {})
        voice = info.get("voice_profile")
        if not voice:
            try:
                voice = get_project(self.db_path, project)["voice_profile"]
            except ProjectNotFound as exc:
                self._toast(str(exc))
                return
        language = info.get("language") or self.settings.language

        out_dir = self.data_dir / "exports" / project
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{chapter:03d}_preview30.wav"
        preview_dir = self.data_dir / "imports"
        preview_dir.mkdir(parents=True, exist_ok=True)
        text_path = preview_dir / f"_preview_{project}_{chapter:03d}.txt"
        text_path.write_text(preview_text, encoding="utf-8")

        args = [
            "speak", str(text_path),
            "--voice", voice,
            "--out", str(out_path),
            "--language", str(language),
        ] + self._fx_args()

        def _on_preview_done(jid):
            if jid is None:
                text_path.unlink(missing_ok=True)
                return
            self._preview_jobs[jid] = {"out": out_path, "text": text_path}
            self.tabs.setCurrentIndex(0)
            self._toast("Generando preview de 30 s…")

        self.start_job(
            f"{project}_{chapter:03d}_preview30",
            args,
            project=project,
            ordinal=chapter,
            allow_duplicate=True,
            on_done=_on_preview_done,
        )

    def _play_preview(self, path: Path) -> None:
        if self.player is None:
            self._toast("QtMultimedia no está disponible.")
            return
        if not path.is_file():
            self._toast("No se generó el archivo de preview.")
            return
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()
        self._set_now_playing(path)
        self._preview_path = path
        if self._preview_timer is not None:
            self._preview_timer.stop()
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._stop_preview)
        self._preview_timer.start(30_000)
        self._toast("Reproduciendo los primeros 30 segundos.")

    def _stop_preview(self) -> None:
        if (
            self.player is not None
            and self._preview_path is not None
            and self.now_playing == self._preview_path
        ):
            self.player.stop()
        self._preview_path = None

    def action_pilot(self) -> None:
        chapter = self._require_chapter()
        if chapter is None:
            return
        project = self.current_project
        out = self.data_dir / "exports" / project / f"{chapter:03d}_piloto.mp3"
        out.parent.mkdir(parents=True, exist_ok=True)
        self.start_job(f"{project}_{chapter:03d}_piloto",
                       ["chapter", "narrate", project, str(chapter), "--out", str(out)]
                       + self._fx_args(),
                       project=project, ordinal=chapter)

    def action_regen_fragment(self) -> None:
        chapter = self._require_chapter()
        if chapter is None:
            return
        project = self.current_project
        frag = self.selected_fragment or self._selected_item_data(self.fragments)
        if frag is None:
            self._toast("Selecciona un fragmento de texto.")
            return
        frag = int(frag)
        out = self.data_dir / "exports" / project / f"{chapter:03d}_fragmento_{frag:02d}_reg.mp3"
        out.parent.mkdir(parents=True, exist_ok=True)
        self.start_job(f"{project}_{chapter:03d}_frag{frag:02d}_reg",
                       ["chapter", "regen", project, str(chapter),
                        "--fragment", str(frag), "--out", str(out)]
                       + self._fx_args(),
                       project=project, ordinal=chapter)

    def action_wav(self) -> None:
        project = self._require_project()
        if project is None:
            return
        out_dir = self.data_dir / "exports" / f"{project}_wav"
        out_dir.mkdir(parents=True, exist_ok=True)
        self.start_job(f"{project}_wav",
                       ["project-narrate", project, "--format", "wav", "--out-dir", str(out_dir)]
                       + self._fx_args(),
                       project=project, ordinal=None)

    def action_mp3(self) -> None:
        project = self._require_project()
        if project is None:
            return
        wav_dir = self.data_dir / "exports" / f"{project}_wav"
        if not wav_dir.is_dir():
            self._toast(f"No existe WAV:\n{wav_dir}\n\nPrimero produce WAV.")
            return
        mp3_dir = self.data_dir / "exports" / f"{project}_mp3"
        mp3_dir.mkdir(parents=True, exist_ok=True)
        self.start_job(f"{project}_mp3",
                       ["fx", "batch", str(wav_dir), "--out-dir", str(mp3_dir),
                        "--normalize-lufs", "-16", "--format", "mp3", "--force"],
                       project=project, ordinal=None)

    def action_cancel(self) -> None:
        jid = self.selected_job_id or self._selected_item_data(self.jobs)
        if jid is None:
            self._toast("Selecciona un trabajo.")
            return

        def _on_cancel_done(code):
            if code == 0:
                self._toast(f"Trabajo #{jid} cancelado.")

        self.run_simple(["job", "cancel", str(jid)], on_done=_on_cancel_done)

    def action_cleanup(self) -> None:
        resp = QMessageBox.question(
            self, "Limpiar trabajos",
            "¿Eliminar los trabajos terminados y sus registros?\n\n"
            "No se toca la caché de audio ni las exportaciones.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        def _on_cleanup_done(code):
            if code == 0:
                self._toast("Trabajos terminados eliminados.")

        self.run_simple(["job", "cleanup", "--all-finished"],
                        on_done=_on_cleanup_done)

    def action_delete_project(self) -> None:
        project = self._require_project()
        if project is None:
            return
        resp = QMessageBox.question(
            self, "Borrar proyecto",
            f"¿Eliminar '{project}' y sus capítulos?\n\nNO se toca voz ni caché global.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_project(self.db_path, project, yes=True)
            self._toast(f"Eliminado: {project}")
        except ProjectNotFound:
            self._toast("Ya no existe.")
        except Exception as exc:
            self._toast(f"Error: {exc}")
        self.current_project = None
        self.current_chapter = None
        self.refresh_all()

    def action_open_exports(self) -> None:
        base = self.data_dir / "exports"
        path = base / self.current_project if self.current_project else base
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def _font_family() -> str:
    families = set(QFontDatabase.families())
    for family in ("Inter", "Segoe UI Variable", "Segoe UI", "Lato", "Noto Sans", "DejaVu Sans"):
        if family in families:
            return family
    return "Sans Serif"


def _make_app_icon(family: str) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    gradient = QLinearGradient(0, 0, 64, 64)
    gradient.setColorAt(0.0, QColor(CYAN))
    gradient.setColorAt(1.0, QColor(PURPLE))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(2, 2, 60, 60), 16, 16)

    font = QFont(family)
    font.setPixelSize(34)
    font.setWeight(QFont.Weight.Black)
    painter.setFont(font)
    painter.setPen(QColor("#06131d"))
    painter.drawText(QRectF(0, 0, 64, 64), Qt.AlignmentFlag.AlignCenter, "V")
    painter.end()
    return QIcon(pixmap)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Aplicar tema (prioridad: argumento CLI > settings guardado > default)
    from voxforge.ui.theme import get_qss, DEFAULT_THEME
    cli_theme = None
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg in ("--night-city", "--theme-night-city"):
                cli_theme = "night_city"
            elif arg in ("--nova", "--theme-nova"):
                cli_theme = "nova"
    initial_theme = cli_theme or DEFAULT_THEME
    app.setStyleSheet(get_qss(initial_theme))
    
    translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    app._translators = []
    for catalog in ("qtbase_es", "qt_es"):
        translator = QTranslator(app)
        if translator.load(catalog, translations):
            app.installTranslator(translator)
            app._translators.append(translator)
    family = _font_family()
    app.setFont(QFont(family, 10))
    app.setWindowIcon(_make_app_icon(family))

    window = VoxForgeGUI()
    screen = app.primaryScreen().availableGeometry()
    window.resize(
        min(1400, screen.width() - 24),
        min(920, screen.height() - 24),
    )
    window.show()
    code = app.exec()
    if getattr(window, "player", None):
        window.player.stop()
    sys.exit(code)


if __name__ == "__main__":
    main()
