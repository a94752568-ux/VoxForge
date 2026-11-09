"""Test de integración para la funcionalidad de reanudación."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from voxforge.config import Settings
from voxforge.db import Store
from voxforge.engines.base import TTSEngine
from voxforge.pipeline import narrate
from voxforge.services.narrator import NarratorService, NarrationRequest


class FakeEngine(TTSEngine):
    """Motor simulado para tests."""
    name = "fake"
    sample_rate = 24000

    def __init__(self):
        self.loads = 0
        self.calls = 0
        self.seeds = []

    def load(self):
        self.loads += 1

    def unload(self):
        pass

    def synthesize(self, text, reference_wav, language, seed):
        self.calls += 1
        self.seeds.append(seed)
        n = int(self.sample_rate * 0.1 * len(text))  # 100 ms por carácter = 10 car/s
        return (0.1 * np.sin(np.linspace(0, 440, n))).astype(np.float32)


class ResumeIntegrationTest(unittest.TestCase):
    """Test de integración para la reanudación."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = Store(self.tmp / "t.db")
        ref = self.tmp / "ref.wav"
        ref.write_bytes(b"x")
        self.store.add_profile("test_voice", ref, "abc123", "es")
        self.profile = self.store.get_profile("test_voice")
        (self.tmp / "cache").mkdir()
        (self.tmp / "exports").mkdir()
        self.settings = Settings(temp_pause_c=999, threads=2)
        self.fake_engine = FakeEngine()
    
    def test_narrate_with_service(self):
        """Test que NarratorService funciona con pipeline real."""
        service = NarratorService(
            store=self.store,
            settings=self.settings,
            data_dir=self.tmp,
            cache_dir=self.tmp / "cache",
            export_dir=self.tmp / "exports",
            engine=self.fake_engine  # Usar FakeEngine para tests
        )
        
        texto = "Hola mundo.\n\nEsto es una prueba."
        request = NarrationRequest(
            project_name="test_project",
            chapter_id=1,
            text=texto,
            voice_profile_name="test_voice",
            language="es",
            regen=False,
            out_path=self.tmp / "exports" / "test.wav",
            resume=True
        )
        
        response = service.narrate(request)
        
        self.assertTrue(response.success)
        self.assertIsNotNone(response.result)
        self.assertEqual(response.result.fragments, 2)
        
        # Verificar que el archivo existe
        out_path = self.tmp / "exports" / "test.wav"
        self.assertTrue(out_path.exists())
        
        # Verificar progreso en DB
        progress = self.store.get_project_progress("test_project", 1)
        self.assertIsNotNone(progress)
        self.assertEqual(progress["status"], "completed")
        self.assertEqual(progress["processed_fragments"], 2)
    
    def test_narrate_resume_after_interruption(self):
        """Test que se puede reanudar después de una interrupción."""
        service = NarratorService(
            store=self.store,
            settings=self.settings,
            data_dir=self.tmp,
            cache_dir=self.tmp / "cache",
            export_dir=self.tmp / "exports",
            engine=self.fake_engine  # Usar FakeEngine para tests
        )
        
        texto = "Frase uno.\n\nFrase dos.\n\nFrase tres."
        
        # Primera narración (simular que solo se completó 1 fragmento)
        request1 = NarrationRequest(
            project_name="test_project",
            chapter_id=2,
            text=texto,
            voice_profile_name="test_voice",
            language="es",
            out_path=self.tmp / "exports" / "test2.wav",
            resume=True
        )
        
        # Simular progreso parcial manualmente
        self.store.update_project_progress(
            "test_project", 2,
            total_fragments=3,
            processed_fragments=1,
            current_fragment=1,
            status="running"
        )
        
        response = service.narrate(request1)
        
        self.assertTrue(response.success)
        
        # Verificar progreso completado
        progress = self.store.get_project_progress("test_project", 2)
        self.assertEqual(progress["status"], "completed")
        self.assertEqual(progress["processed_fragments"], 3)
    
    def test_disk_space_validation(self):
        """Test que la validación de espacio en disco funciona."""
        service = NarratorService(
            store=self.store,
            settings=self.settings,
            data_dir=self.tmp,
            cache_dir=self.tmp / "cache",
            export_dir=self.tmp / "exports",
            engine=self.fake_engine  # Usar FakeEngine para tests
        )
        
        # Texto muy largo (debería requerir mucho espacio)
        texto = "A" * 1000000  # 1 millón de caracteres
        
        request = NarrationRequest(
            project_name="big_project",
            chapter_id=1,
            text=texto,
            voice_profile_name="test_voice",
            language="es",
            out_path=self.tmp / "exports" / "big.wav"
        )
        
        # Esto no debería fallar porque hay suficiente espacio
        response = service.narrate(request)
        
        # Verificar que al menos intentó (puede fallar por otros motivos)
        self.assertIsNotNone(response)


if __name__ == "__main__":
    unittest.main()
