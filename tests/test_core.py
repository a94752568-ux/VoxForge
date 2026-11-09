"""Pruebas sin XTTS: usan un motor simulado, así que corren en segundos y sin descargar nada."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from voxforge.config import Settings
from voxforge.db import Store
from voxforge.engines.base import TTSEngine
from voxforge.pipeline import narrate
from voxforge.textutil import split_text
from voxforge.thermal import wait_if_hot


class FakeEngine(TTSEngine):
    name = "fake"
    sample_rate = 24000

    def __init__(self, plan=None):
        self.loads = 0
        self.calls = 0
        self.seeds = []
        self.plan = list(plan or [])  # multiplicador de duración por llamada (1.0 = normal)

    def load(self):
        self.loads += 1

    def unload(self):
        pass

    def synthesize(self, text, reference_wav, language, seed):
        self.calls += 1
        self.seeds.append(seed)
        factor = self.plan.pop(0) if self.plan else 1.0
        n = int(self.sample_rate * 0.1 * factor * len(text))  # 100 ms por carácter = 10 car/s
        return (0.1 * np.sin(np.linspace(0, 440, n))).astype(np.float32)


class TextSplitTests(unittest.TestCase):
    def test_respeta_limite_y_marca_parrafos(self):
        largo = "Esta es una frase bastante larga, con varias comas, que sigue y sigue; " * 8
        texto = f"Hola. ¿Qué tal? Muy bien.\n\n{largo}\n\nFin."
        chunks = split_text(texto, 100)
        self.assertTrue(all(len(c.text) <= 100 for c in chunks))
        self.assertEqual(sum(c.paragraph_end for c in chunks), 3)
        self.assertTrue(chunks[-1].paragraph_end)

    def test_texto_vacio(self):
        self.assertEqual(split_text("  \n\n  "), [])


class ThermalTests(unittest.TestCase):
    def test_espera_hasta_enfriar(self):
        temps = iter([95.0, 88.0, 79.0])
        esperado = wait_if_hot(90, 80, log=lambda m: None, poll_s=5,
                               read=lambda: next(temps), sleep=lambda s: None)
        self.assertEqual(esperado, 10.0)

    def test_no_espera_si_esta_frio(self):
        self.assertEqual(wait_if_hot(90, 80, log=lambda m: None, read=lambda: 60.0), 0.0)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = Store(self.tmp / "t.db")
        ref = self.tmp / "ref.wav"
        ref.write_bytes(b"x")
        self.store.add_profile("yo", ref, "abc123", "es")
        self.profile = self.store.get_profile("yo")
        (self.tmp / "cache").mkdir()

    def run_narrate(self, engine, text):
        return narrate(text, self.profile, engine, self.store, Settings(temp_pause_c=999),
                       self.tmp / "cache", self.tmp / "out.wav", log=lambda m: None)

    def test_segunda_ejecucion_usa_cache(self):
        texto = "Primera frase. Segunda frase.\n\nOtro párrafo."
        e1 = FakeEngine()
        r1 = self.run_narrate(e1, texto)
        self.assertEqual((r1.generated, r1.cached), (2, 0))
        e2 = FakeEngine()
        r2 = self.run_narrate(e2, texto)
        self.assertEqual((r2.generated, r2.cached, e2.calls, e2.loads), (0, 2, 0, 0))
        self.assertAlmostEqual(r1.audio_s, r2.audio_s, places=3)

    def test_cambiar_texto_regenera_solo_lo_nuevo(self):
        self.run_narrate(FakeEngine(), "Frase uno.\n\nFrase dos.")
        e = FakeEngine()
        r = self.run_narrate(e, "Frase uno.\n\nFrase tres.")
        self.assertEqual((r.generated, r.cached), (1, 1))

    def test_fragmento_anomalo_se_reintenta_con_otra_semilla(self):
        texto = "Esta frase tiene bastantes caracteres para que se aplique el control de calidad."
        e = FakeEngine(plan=[3.0, 1.0])  # primer intento 3 veces más largo de lo normal
        r = self.run_narrate(e, texto)
        self.assertEqual((e.calls, r.retried, r.doubtful), (2, 1, 0))
        self.assertEqual(e.seeds[1], e.seeds[0] + 1)
        fila = self.store.conn.execute("SELECT attempt, ok FROM fragments").fetchone()
        self.assertEqual((fila["attempt"], fila["ok"]), (1, 1))

    def test_si_todos_los_intentos_fallan_queda_dudoso_y_no_se_repite(self):
        texto = "Esta frase tiene bastantes caracteres para que se aplique el control de calidad."
        e = FakeEngine(plan=[3.0, 3.0, 3.0])
        r = self.run_narrate(e, texto)
        self.assertEqual((e.calls, r.retried, r.doubtful), (3, 1, 1))
        e2 = FakeEngine()
        r2 = self.run_narrate(e2, texto)  # no debe volver a gastar cálculo
        self.assertEqual((e2.calls, r2.cached, r2.doubtful), (0, 1, 1))

    def test_fragmento_antiguo_anomalo_en_cache_se_regenera(self):
        texto = "Esta frase tiene bastantes caracteres para que se aplique el control de calidad."
        self.run_narrate(FakeEngine(plan=[3.0, 3.0, 3.0]), texto)  # deja un fragmento dudoso (ok=0)
        self.store.conn.execute("UPDATE fragments SET ok = 1")     # simula una fila antigua sin control
        self.store.conn.commit()
        e = FakeEngine()
        r = self.run_narrate(e, texto)
        self.assertEqual((e.calls, r.generated, r.doubtful), (1, 1, 0))

    def test_regen_fuerza_nueva_semilla(self):
        texto = "Esta frase tiene bastantes caracteres para que se aplique el control de calidad."
        e1 = FakeEngine(); self.run_narrate(e1, texto)
        e2 = FakeEngine()
        narrate(texto, self.profile, e2, self.store, Settings(temp_pause_c=999), self.tmp / "cache",
                self.tmp / "out.wav", regen=True, log=lambda m: None)
        self.assertEqual(e2.seeds[0], e1.seeds[0] + 1)

    def test_perfil_duplicado_falla(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.add_profile("yo", Path("x"), "h", "es")


class ResumeTests(unittest.TestCase):
    """Tests para la funcionalidad de reanudación de narraciones."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = Store(self.tmp / "t.db")
        ref = self.tmp / "ref.wav"
        ref.write_bytes(b"x")
        self.store.add_profile("yo", ref, "abc123", "es")
        self.profile = self.store.get_profile("yo")
        (self.tmp / "cache").mkdir()
    
    def run_narrate(self, engine, text, project_name="test", chapter_id=1, resume=True):
        return narrate(
            text, self.profile, engine, self.store, Settings(temp_pause_c=999),
            self.tmp / "cache", self.tmp / "out.wav",
            project_name=project_name,
            chapter_id=chapter_id,
            resume=resume,
            log=lambda m: None
        )
    
    def test_progreso_guardado_en_db(self):
        """Test que el progreso se guarda en la base de datos."""
        texto = "Frase uno.\n\nFrase dos.\n\nFrase tres."
        e = FakeEngine()
        self.run_narrate(e, texto)
        
        # Verificar que se guardó el progreso
        progress = self.store.get_project_progress("test", 1)
        self.assertIsNotNone(progress)
        self.assertEqual(progress["status"], "completed")
        self.assertEqual(progress["processed_fragments"], 3)
    
    def test_reanudacion_desde_medio(self):
        """Test que se puede reanudar desde la mitad."""
        texto = "Frase uno.\n\nFrase dos.\n\nFrase tres."
        
        # Simular progreso parcial
        self.store.update_project_progress(
            "test", 1, total_fragments=3, processed_fragments=1,
            current_fragment=1, status="running"
        )
        
        e = FakeEngine()
        r = self.run_narrate(e, texto, resume=True)
        
        # Debería haber procesado solo 2 fragmentos (saltando el primero)
        self.assertEqual(r.generated, 2)
        
        # Verificar que el progreso se completó
        progress = self.store.get_project_progress("test", 1)
        self.assertEqual(progress["status"], "completed")
        self.assertEqual(progress["processed_fragments"], 3)
    
    def test_no_reanudar_si_resume_false(self):
        """Test que no reanuda si resume=False."""
        texto = "Frase uno.\n\nFrase dos.\n\nFrase tres."
        
        # Simular progreso parcial
        self.store.update_project_progress(
            "test", 1, total_fragments=3, processed_fragments=1,
            current_fragment=1, status="running"
        )
        
        e = FakeEngine()
        r = self.run_narrate(e, texto, resume=False)
        
        # Debería haber procesado todos los fragmentos
        self.assertEqual(r.generated, 3)


class UtilsTests(unittest.TestCase):
    """Tests para utilidades."""
    
    def test_check_disk_space_ok(self):
        """Test que check_disk_space no lanza error con suficiente espacio."""
        from voxforge.utils import check_disk_space
        tmp = Path(tempfile.mkdtemp())
        # 1KB debería estar disponible
        check_disk_space(tmp, 1024)  # No debería lanzar
    
    def test_estimate_audio_size(self):
        """Test que estimate_audio_size calcula correctamente."""
        from voxforge.utils import estimate_audio_size_bytes
        # 100 caracteres a 10 cps = 10 segundos
        # 24000 Hz * 2 bytes * 1 canal * 10 segundos = 480000 bytes
        size = estimate_audio_size_bytes(100, sample_rate=24000, cps=10.0)
        self.assertAlmostEqual(size, 24000 * 2 * 10, delta=1000)


if __name__ == "__main__":
    unittest.main()
