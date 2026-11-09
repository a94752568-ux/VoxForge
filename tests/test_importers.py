"""Pruebas de importación: PDF con texto embebido y PDF escaneado con OCR."""
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

try:
    import pymupdf
    from PIL import Image
except ImportError:  # pragma: no cover - el entorno normal las tiene
    pymupdf = None
    Image = None

from voxforge.importers import ImporterError, extract_pdf, extract_text


class FakePytesseract(types.ModuleType):
    """Sustituye a pytesseract para no depender de tesseract en los tests."""

    class TesseractNotFoundError(RuntimeError):
        pass

    class TesseractError(RuntimeError):
        pass

    def __init__(self, text: str = "Texto reconocido por OCR de prueba.", texts=None):
        super().__init__("pytesseract")
        self.text = text
        self.texts = list(texts) if texts is not None else None
        self.calls: list[tuple[tuple[int, int], str]] = []

    def get_languages(self, config: str = "") -> list[str]:
        return ["eng", "spa"]

    def image_to_string(self, image, lang: str = "eng") -> str:
        self.calls.append((image.size, lang))
        if self.texts is None:
            return self.text
        return self.texts[min(len(self.calls) - 1, len(self.texts) - 1)]


def _text_pdf(path: Path, text: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def _scanned_pdf(path: Path) -> None:
    """PDF de una página que solo contiene una imagen (sin capa de texto)."""
    buffer = io.BytesIO()
    Image.new("RGB", (320, 120), "white").save(buffer, format="PNG")

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(0, 0, 320, 120), stream=buffer.getvalue())
    doc.save(str(path))
    doc.close()


def _scanned_pdf_pages(path: Path, pages: int) -> None:
    """PDF de varias páginas, cada una con una imagen y sin texto embebido."""
    buffer = io.BytesIO()
    Image.new("RGB", (320, 120), "white").save(buffer, format="PNG")
    data = buffer.getvalue()

    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 320, 120), stream=data)
    doc.save(str(path))
    doc.close()


@unittest.skipIf(pymupdf is None, "pymupdf/Pillow no están instalados")
class PdfTests(unittest.TestCase):
    def test_pdf_con_texto_embebido_no_usa_ocr(self):
        fake = FakePytesseract()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "texto.pdf"
            _text_pdf(path, "Hola desde un PDF con texto embebido.")
            with mock.patch.dict(sys.modules, {"pytesseract": fake}):
                text = extract_pdf(path)
        self.assertIn("texto embebido", text)
        self.assertEqual(fake.calls, [])

    def test_pdf_escaneado_aplica_ocr_en_espanol(self):
        fake = FakePytesseract()
        logs: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "escaneado.pdf"
            _scanned_pdf(path)
            with mock.patch.dict(sys.modules, {"pytesseract": fake}):
                text = extract_pdf(path, lang="es", log=logs.append)
        self.assertIn("Texto reconocido por OCR", text)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0][1], "spa")
        self.assertTrue(any("OCR" in line for line in logs))

    def test_ocr_desactivado_da_error_claro(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "escaneado.pdf"
            _scanned_pdf(path)
            with self.assertRaises(ImporterError) as ctx:
                extract_pdf(path, ocr=False)
        self.assertIn("OCR activado", str(ctx.exception))

    def test_ocr_sin_texto_suficiente_da_error(self):
        fake = FakePytesseract(text="x")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "escaneado.pdf"
            _scanned_pdf(path)
            with mock.patch.dict(sys.modules, {"pytesseract": fake}):
                with self.assertRaises(ImporterError) as ctx:
                    extract_pdf(path)
        self.assertIn("no extrajo texto suficiente", str(ctx.exception))

    def test_ocr_limpia_folios_y_encabezados(self):
        fake = FakePytesseract(
            texts=[f"POPOL VUH\nTexto de la página {i}.\n{i + 2}" for i in range(1, 9)]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ocho_paginas.pdf"
            _scanned_pdf_pages(path, 8)
            with mock.patch.dict(sys.modules, {"pytesseract": fake}):
                text = extract_pdf(path)
        self.assertEqual(text.count("POPOL VUH"), 1)
        self.assertIn("Texto de la página 8.", text)
        self.assertNotRegex(text, r"(?m)^3$")

    def test_extract_text_delega_el_ocr(self):
        fake = FakePytesseract()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "escaneado.pdf"
            _scanned_pdf(path)
            with mock.patch.dict(sys.modules, {"pytesseract": fake}):
                text = extract_text(path, lang="spa")
        self.assertIn("Texto reconocido por OCR", text)

    def test_tesseract_ausente_da_error_claro(self):
        class BrokenPytesseract(FakePytesseract):
            def image_to_string(self, image, lang: str = "eng") -> str:
                raise self.TesseractNotFoundError("tesseract no está instalado")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "escaneado.pdf"
            _scanned_pdf(path)
            with mock.patch.dict(sys.modules, {"pytesseract": BrokenPytesseract()}):
                with self.assertRaises(ImporterError) as ctx:
                    extract_pdf(path)
        self.assertIn("tesseract-ocr", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
