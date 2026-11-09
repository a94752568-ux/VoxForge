"""Pruebas de la preparación de muestras con una señal sintética (voz armónica + ruido blanco)."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from voxforge.audioqa import analyze
from voxforge.prepare import normalize_peak, prepare, trim_and_compact

SR = 24000


def harmonic_speech(dur=20.0, noise_db=-35.0, seed=3, lead=1.5, tail=1.2):
    rng = np.random.default_rng(seed)
    t = np.arange(int(SR * dur)) / SR
    f0 = 140 + 25 * np.sin(2 * np.pi * 0.3 * t)
    phase = 2 * np.pi * np.cumsum(f0) / SR
    sig = sum((1 / h) * np.sin(h * phase) for h in range(1, 12))
    env = np.clip(np.sin(2 * np.pi * 0.45 * t) * 1.6, 0, 1) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t) ** 2)
    x = 0.12 * env * sig / np.abs(sig).max() * 3
    x[: int(lead * SR)] = 0
    x[len(x) - int(tail * SR):] = 0
    return np.clip(x + rng.normal(0, 10 ** (noise_db / 20), len(t)), -1, 1).astype(np.float32)


def value(checks, name):
    return float(next(c.value for c in checks if c.name == name).split()[0])


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "in.wav"
        sf.write(self.src, harmonic_speech(), SR)

    def test_mejora_la_relacion_senal_ruido_y_normaliza(self):
        dest = self.tmp / "out.wav"
        res = prepare(self.src, dest, nr=12)
        audio, sr = sf.read(dest, dtype="float32")
        antes = analyze(sf.read(self.src, dtype="float32")[0], SR)
        despues = analyze(audio, sr)
        self.assertGreater(value(despues, "Relación señal/ruido"), value(antes, "Relación señal/ruido") + 5)
        self.assertAlmostEqual(20 * np.log10(np.abs(audio).max()), -3.0, delta=0.3)
        self.assertLess(res.after_s, res.before_s)

    def test_recorta_extremos(self):
        dest = self.tmp / "out.wav"
        prepare(self.src, dest, nr=0)
        despues = analyze(sf.read(dest, dtype="float32")[0], SR)
        self.assertLessEqual(value(despues, "Silencio en los extremos"), 0.6)

    def test_sin_reduccion_de_ruido_no_cambia_la_relacion_senal_ruido(self):
        dest = self.tmp / "out.wav"
        prepare(self.src, dest, nr=0)
        antes = value(analyze(sf.read(self.src, dtype="float32")[0], SR), "Relación señal/ruido")
        despues = value(analyze(sf.read(dest, dtype="float32")[0], SR), "Relación señal/ruido")
        self.assertAlmostEqual(antes, despues, delta=2.0)

    def test_no_modifica_el_original(self):
        antes = self.src.read_bytes()
        prepare(self.src, self.tmp / "out.wav")
        self.assertEqual(antes, self.src.read_bytes())

    def test_pausas_largas_se_acortan(self):
        audio = harmonic_speech(lead=0.0, tail=0.0)
        audio[int(6 * SR):int(10 * SR)] = np.random.default_rng(9).normal(0, 0.0177, int(4 * SR))  # 4 s de solo ruido
        out = trim_and_compact(audio, SR, max_pause_s=1.0)
        self.assertLess(len(out) / SR, len(audio) / SR - 2.5)

    def test_normalizacion_limita_la_ganancia(self):
        quiet = np.full(24000, 1e-3, dtype=np.float32)
        _, gain = normalize_peak(quiet, -3.0, max_gain_db=24.0)
        self.assertLessEqual(gain, 24.0)


if __name__ == "__main__":
    unittest.main()
