"""Prueba de humo de la GUI: construcción, avisos y arranque de trabajos."""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
import unittest
from pathlib import Path
from unittest import mock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from PySide6.QtWidgets import QApplication
    import gui
except (ImportError, SystemExit):
    QApplication = None
    gui = None


@unittest.skipUnless(QApplication is not None, "PySide6 no está instalado")
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"VOXFORGE_HOME": self.tmp.name})
        self.env.start()
        self.win = gui.VoxForgeGUI()
        self.win.show()
        for _ in range(5):
            self.app.processEvents()

    def tearDown(self):
        self.win.tail_timer.stop()
        self.win.fx_timer.stop()
        if getattr(self.win, "player", None):
            self.win.player.stop()
        self.win.close()
        self.win.deleteLater()
        for _ in range(5):
            self.app.processEvents()
        self.env.stop()
        self.tmp.cleanup()

    def test_aviso_no_falla(self):
        self.win.log.clear()
        self.win._toast("Aviso de prueba")
        self.assertIn("Aviso de prueba", self.win.log.toPlainText())

    def test_error_del_reproductor_no_falla(self):
        self.win.log.clear()

        class Error:
            name = "TestError"

        self.win._on_player_error(Error(), "fallo simulado")
        self.assertIn("fallo simulado", self.win.log.toPlainText())

    def test_iniciar_trabajo_avisa_sin_fallar(self):
        self.win.log.clear()

        class Result:
            returncode = 0
            stdout = "Trabajo iniciado: id=999 status=running pid=1\n"
            stderr = ""

        with mock.patch.object(gui.subprocess, "run", return_value=Result()):
            self.win.start_job("prueba", ["status"])

        self.assertIn("en marcha", self.win.log.toPlainText())

    def test_dialogo_de_importacion_valida_y_devuelve_datos(self):
        from PySide6.QtWidgets import QDialog

        libro = Path(self.tmp.name) / "mi_libro.txt"
        libro.write_text("Contenido de prueba.", encoding="utf-8")

        dialog = gui.ImportBookDialog(None, ["yo_limpia", "yo"], "yo_limpia")
        dialog._set_file(libro)
        self.assertEqual(dialog.name_edit.text(), "mi_libro")
        self.assertTrue(dialog.import_btn.isEnabled())

        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        data = dialog.data()
        self.assertEqual(data["path"], libro)
        self.assertEqual(data["name"], "mi_libro")
        self.assertEqual(data["voice"], "yo_limpia")

    def test_calculo_de_progreso_y_estimacion(self):
        job = {
            "id": 1,
            "status": "running",
            "name": "prueba",
            "command": json.dumps(["chapter", "narrate", "p", "1"]),
        }
        progress = self.win._compute_progress(job, "[4/10] en caché\n")
        self.assertEqual(progress["value"], 40)
        self.assertEqual(progress["text"], "Fragmento 4/10")

        import_job = {
            "id": 2,
            "status": "running",
            "name": "importar",
            "command": json.dumps(["project", "import", "p", "--file", "libro.pdf"]),
        }
        ocr = self.win._compute_progress(import_job, "  OCR 25/100 páginas\n")
        self.assertEqual(ocr["value"], 25)
        self.assertEqual(ocr["text"], "OCR 25/100 páginas")

        self.assertEqual(gui._fmt_clock(65), "01:05")
        self.assertEqual(gui._fmt_duration(90), "2 min")

        started = (datetime.now(timezone.utc) - timedelta(seconds=60)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        elapsed = gui._job_elapsed({"started_at": started})
        self.assertAlmostEqual(elapsed, 60, delta=2)

    def test_dialogos_de_voz_y_editor_de_capitulo(self):
        from voxforge.projects import add_chapter, create_project, get_chapter

        manager = gui.VoiceManagerDialog(self.win, self.win.db_path, self.win.data_dir)
        self.assertEqual(manager.voice_count.text(), "0")
        manager.close()

        create_project(self.win.db_path, "demo", "voz", "es")
        chapter_file = Path(self.tmp.name) / "capitulo_editor.txt"
        chapter_file.write_text("Primera frase.\n\n[pausa=1.5s]\n\nSegunda frase.", encoding="utf-8")
        add_chapter(self.win.db_path, "demo", "Capítulo de prueba", chapter_file)
        chapter = get_chapter(self.win.db_path, "demo", 1)

        editor = gui.ChapterEditorDialog(self.win, "demo", chapter, self.win.settings)
        self.assertIn("fragmentos", editor.stats.text())
        self.assertEqual(editor.title_edit.text(), "Capítulo de prueba")
        editor.close()


if __name__ == "__main__":
    unittest.main()
