"""Pruebas de la limpieza de texto OCR (guiones, folios y encabezados)."""
import unittest

from voxforge.ocrclean import clean_ocr_pages, clean_ocr_text


class HyphenTests(unittest.TestCase):
    def test_une_palabras_cortadas_por_guion(self):
        result = clean_ocr_text(
            "Los quichés de Gua-\ntemala son.\n\nOtra lí-\nnea distinta."
        )
        self.assertIn("Guatemala", result.text)
        self.assertIn("línea", result.text)
        self.assertNotIn("Gua-\n", result.text)
        self.assertEqual(result.hyphen_joins, 2)

    def test_no_une_un_guion_antes_de_mayuscula(self):
        result = clean_ocr_text("Vucub-\nCaquix era un señor.")
        self.assertIn("Vucub-\nCaquix", result.text)
        self.assertEqual(result.hyphen_joins, 0)

    def test_une_palabra_entre_dos_paginas(self):
        result = clean_ocr_pages(["Final de la pági-", "na siguiente."])
        self.assertIn("página siguiente", result.text)
        self.assertEqual(result.hyphen_joins, 1)


class PageTests(unittest.TestCase):
    def test_elimina_folios_y_encabezados_repetidos(self):
        pages = [f"POPOL VUH\nTexto de la página {i}.\n{i + 2}" for i in range(1, 9)]
        result = clean_ocr_pages(pages)

        self.assertEqual(result.page_numbers_removed, 8)
        self.assertEqual(result.headers_removed, 7)
        self.assertTrue(result.text.startswith("POPOL VUH\nTexto de la página 1."))
        self.assertIn("Texto de la página 8.", result.text)
        self.assertNotIn("POPOL VUH\nTexto de la página 2.", result.text)

    def test_conserva_titulos_de_capitulo_poco_frecuentes(self):
        pages = []
        for i in range(1, 11):
            heading = "CAPITULO PRIMERO" if i <= 4 else f"Texto {i}."
            pages.append(f"{heading}\nCuerpo de la página {i}.\n{i + 1}")

        result = clean_ocr_pages(pages)
        self.assertEqual(result.text.count("CAPITULO PRIMERO"), 4)
        self.assertEqual(result.headers_removed, 0)

    def test_elimina_numero_aislado_entre_lineas_en_blanco(self):
        result = clean_ocr_text("Texto.\n\n17\n\nMás texto.")
        self.assertNotIn("\n17\n", result.text)
        self.assertEqual(result.page_numbers_removed, 1)

    def test_no_elimina_numeros_que_no_son_folios(self):
        # Un año de cuatro cifras al principio de la página no es un folio.
        result = clean_ocr_text("1492\nAño del descubrimiento.")
        self.assertIn("1492", result.text)

    def test_elimina_lineas_decorativas_en_los_bordes(self):
        result = clean_ocr_pages(["|\nTexto útil.\n***"])
        self.assertEqual(result.noise_lines_removed, 2)
        self.assertEqual(result.text, "Texto útil.")

    def test_sin_paginas_no_falla(self):
        result = clean_ocr_pages([])
        self.assertEqual(result.text, "")


if __name__ == "__main__":
    unittest.main()
