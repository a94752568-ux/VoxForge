"""Prueba la mecánica de grabación con una fuente sintética de ffmpeg (sin micrófono)."""
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from voxforge.audioqa import room_noise
from voxforge.recorder import RecordingError, record_fixed, record_until

FUENTE = ["-re", "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000"]


class RecorderTests(unittest.TestCase):
    def test_record_until_cierra_el_archivo_al_terminar_la_espera(self):
        out = Path(tempfile.mkdtemp()) / "toma.wav"
        record_until(FUENTE, out, lambda: time.sleep(1.5))
        self.assertTrue(out.exists())
        self.assertGreater(sf.info(out).duration, 0.8)
        self.assertLess(sf.info(out).duration, 4.0)

    def test_record_fixed_dura_lo_pedido(self):
        out = Path(tempfile.mkdtemp()) / "sala.wav"
        record_fixed(FUENTE, out, 2)
        self.assertAlmostEqual(sf.info(out).duration, 2.0, delta=0.3)

    def test_fuente_invalida_da_error_claro(self):
        out = Path(tempfile.mkdtemp()) / "x.wav"
        with self.assertRaises(RecordingError):
            record_fixed(["-f", "lavfi", "-i", "filtro_que_no_existe"], out, 1)


class RoomNoiseTests(unittest.TestCase):
    def rng_noise(self, db):
        rng = np.random.default_rng(1)
        return rng.normal(0, 10 ** (db / 20), 24000 * 3).astype(np.float32)

    def test_sala_silenciosa(self):
        self.assertEqual(room_noise(self.rng_noise(-62)).status, "OK")

    def test_sala_con_algo_de_ruido(self):
        self.assertEqual(room_noise(self.rng_noise(-50)).status, "AVISO")

    def test_sala_ruidosa(self):
        self.assertEqual(room_noise(self.rng_noise(-38)).status, "MAL")

    def test_sin_senal(self):
        self.assertEqual(room_noise(np.zeros(24000 * 3, dtype=np.float32)).status, "MAL")


if __name__ == "__main__":
    unittest.main()
