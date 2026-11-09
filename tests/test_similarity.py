"""Pruebas de la comparación de voces con una huella simulada (espectro medio normalizado)."""
import unittest

import numpy as np

from voxforge.similarity import compare, cosine, window_slices

SR = 24000


def fake_embed(audio, sr):
    """Huella de juguete: espectro medio (en dB) en 64 bandas y centrado. Mismo timbre = huella parecida."""
    spec = np.abs(np.fft.rfft(audio[: sr * 8]))
    bands = np.array_split(spec, 64)
    v = 20 * np.log10(np.array([b.mean() for b in bands]) + 1e-9)
    v = v - v.mean()
    return v / (np.linalg.norm(v) + 1e-12)


def tone(freqs, dur=30.0, seed=0, level=0.1):
    rng = np.random.default_rng(seed)
    t = np.arange(int(SR * dur)) / SR
    x = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
    return (level * x + rng.normal(0, 0.002, len(t))).astype(np.float32)


class SimilarityTests(unittest.TestCase):
    def test_ventanas(self):
        self.assertEqual(len(window_slices(SR * 30, SR, 8.0)), 4)       # 8+8+8+6
        self.assertEqual(len(window_slices(SR * 33, SR, 8.0)), 4)       # el resto de 1 s se descarta
        self.assertEqual(len(window_slices(SR * 2, SR, 8.0)), 1)        # única ventana, aunque corta

    def test_coseno(self):
        self.assertAlmostEqual(cosine(np.ones(4), np.ones(4)), 1.0)
        self.assertAlmostEqual(cosine(np.array([1, 0]), np.array([0, 1])), 0.0)
        self.assertEqual(cosine(np.zeros(3), np.ones(3)), 0.0)

    def test_misma_voz_puntua_mas_que_otra(self):
        ref = tone([120, 240, 360, 480])
        ref_emb = fake_embed(ref, SR)
        misma = compare(fake_embed, ref_emb, tone([120, 240, 360, 480], seed=5), SR)
        otra = compare(fake_embed, ref_emb, tone([300, 900, 1500, 2100], seed=6), SR)
        self.assertGreater(misma.mean, otra.mean + 0.2)
        self.assertEqual(misma.windows, 4)

    def test_minima_detecta_un_tramo_que_se_desvia(self):
        ref = tone([120, 240, 360, 480])
        ref_emb = fake_embed(ref, SR)
        audio = tone([120, 240, 360, 480], seed=7)
        audio[SR * 8:SR * 16] = tone([300, 900, 1500, 2100], dur=8.0, seed=8)  # 2.ª ventana distinta
        r = compare(fake_embed, ref_emb, audio, SR)
        self.assertLess(r.minimum, r.mean - 0.1)

    def test_audio_mudo_no_falla(self):
        r = compare(fake_embed, fake_embed(tone([200]), SR), np.zeros(SR * 10, dtype=np.float32), SR)
        self.assertEqual((r.windows, r.mean), (0, 0.0))


if __name__ == "__main__":
    unittest.main()
