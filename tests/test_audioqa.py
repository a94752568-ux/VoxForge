"""Pruebas del análisis de calidad con señales sintéticas tipo habla (ráfagas de ruido)."""
import unittest

import numpy as np

from voxforge.audioqa import analyze, verdict

SR = 24000


def speechlike(dur=15.0, level=0.1, noise_db=-65.0, seed=0):
    """Ráfagas de ruido (≈ habla) sobre un ruido de fondo constante."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(SR * dur)) / SR
    env = (np.sin(2 * np.pi * 0.5 * t) > -0.2).astype(np.float64)
    carrier = rng.normal(0, 1, len(t))
    noise = rng.normal(0, 10 ** (noise_db / 20), len(t))
    return np.clip(level * env * carrier + noise, -1, 1).astype(np.float32)


def status(checks, name):
    return next(c.status for c in checks if c.name == name)


class AudioQaTests(unittest.TestCase):
    def test_muestra_limpia_es_adecuada(self):
        checks = analyze(speechlike(), SR)
        self.assertEqual({c.status for c in checks}, {"OK"})
        self.assertIn("adecuada", verdict(checks))

    def test_muestra_corta_es_mala(self):
        self.assertEqual(status(analyze(speechlike(dur=3), SR), "Duración"), "MAL")

    def test_mucho_ruido_baja_la_relacion_senal_ruido(self):
        checks = analyze(speechlike(noise_db=-28), SR)
        self.assertEqual(status(checks, "Relación señal/ruido"), "MAL")
        self.assertIn("No recomendable", verdict(checks))

    def test_recorte_se_detecta(self):
        self.assertEqual(status(analyze(speechlike(level=0.6), SR), "Recorte"), "MAL")

    def test_pausa_larga_se_avisa(self):
        audio = speechlike()
        audio[int(5 * SR):int(8.5 * SR)] = 0.0  # 3,5 s de silencio en mitad
        self.assertEqual(status(analyze(audio, SR), "Pausa más larga"), "AVISO")

    def test_silencio_en_los_extremos(self):
        audio = np.concatenate([np.zeros(int(2.5 * SR), dtype=np.float32), speechlike()])
        self.assertEqual(status(analyze(audio, SR), "Silencio en los extremos"), "AVISO")

    def test_silencio_total_avisa_de_que_no_hay_senal(self):
        checks = analyze(np.zeros(SR * 12, dtype=np.float32), SR)
        self.assertEqual(status(checks, "Señal"), "MAL")
        self.assertIn("No recomendable", verdict(checks))

    def test_ruido_extremo_no_genera_avisos_derivados_enganosos(self):
        checks = analyze(speechlike(noise_db=-28), SR)
        self.assertEqual(status(checks, "Relación señal/ruido"), "MAL")
        self.assertEqual(next(c.value for c in checks if c.name == "Habla activa"), "n/d")
        self.assertEqual([c.status for c in checks if c.status == "AVISO"], [])


if __name__ == "__main__":
    unittest.main()
