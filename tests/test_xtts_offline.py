"""Comprueba el modo sin conexión del adaptador XTTS con torch y TTS simulados."""
import os
import sys
import types
import unittest
from unittest import mock

from voxforge.engines.base import ModelUnavailableError
from voxforge.engines.xtts import XttsEngine


def _fake_modules(tts_factory):
    torch = types.ModuleType("torch")
    torch.set_num_threads = lambda n: None
    torch.manual_seed = lambda s: None
    tts_pkg = types.ModuleType("TTS")
    api = types.ModuleType("TTS.api")
    api.TTS = tts_factory
    return {"torch": torch, "TTS": tts_pkg, "TTS.api": api}


class XttsOfflineTests(unittest.TestCase):
    def test_sin_conexion_por_defecto(self):
        with mock.patch.dict(sys.modules, _fake_modules(lambda name: object())), \
                mock.patch.dict(os.environ, {}):
            os.environ.pop("HF_HUB_OFFLINE", None)
            XttsEngine().load()
            self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
            self.assertEqual(os.environ["TRANSFORMERS_OFFLINE"], "1")

    def test_descarga_permite_conexion(self):
        with mock.patch.dict(sys.modules, _fake_modules(lambda name: object())), \
                mock.patch.dict(os.environ, {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}):
            XttsEngine(offline=False).load()
            self.assertNotIn("HF_HUB_OFFLINE", os.environ)
            self.assertNotIn("TRANSFORMERS_OFFLINE", os.environ)

    def test_error_claro_si_el_modelo_no_esta(self):
        def sin_modelo(name):
            raise OSError("no está en la caché")

        with mock.patch.dict(sys.modules, _fake_modules(sin_modelo)), mock.patch.dict(os.environ, {}):
            with self.assertRaises(ModelUnavailableError) as ctx:
                XttsEngine().load()
            self.assertIn("model download", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
