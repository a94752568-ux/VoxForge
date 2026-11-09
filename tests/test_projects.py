"""Pruebas de proyectos y capítulos, incluida la edición de texto."""
import tempfile
import unittest
from pathlib import Path

from voxforge.projects import (
    ProjectError,
    add_chapter,
    create_project,
    get_chapter,
    update_chapter,
)


class ChapterUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "voxforge.db"
        self.src = Path(self.tmp.name) / "capitulo.txt"
        self.src.write_text("Texto inicial del capítulo.", encoding="utf-8")
        create_project(self.db, "demo", "voz", "es")
        add_chapter(self.db, "demo", "Original", self.src)

    def tearDown(self):
        self.tmp.cleanup()

    def test_actualiza_titulo_y_texto(self):
        result = update_chapter(
            self.db,
            "demo",
            1,
            title="El faro",
            text="Texto nuevo.\n\nOtra línea.",
        )
        self.assertEqual(result["title"], "El faro")
        chapter = get_chapter(self.db, "demo", 1)
        self.assertEqual(chapter["title"], "El faro")
        self.assertIn("Texto nuevo", chapter["text"])

    def test_rechaza_texto_vacio(self):
        with self.assertRaises(ProjectError):
            update_chapter(self.db, "demo", 1, text="   ")

    def test_rechaza_titulo_vacio(self):
        with self.assertRaises(ProjectError):
            update_chapter(self.db, "demo", 1, title="  ")

    def test_capitulo_inexistente(self):
        with self.assertRaises(Exception):
            update_chapter(self.db, "demo", 99, title="No existe")


if __name__ == "__main__":
    unittest.main()
