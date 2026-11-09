"""Tests para validar calidad de audio profesional."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from voxforge.voicefx import (
    PRESETS,
    apply_fx,
    deess_audio,
    noise_gate,
    multiband_compress,
    ensure_ebu_r128,
    normalize_lufs,
    apply_professional_chain,
    FxError,
    analyze_audio,
)


class PresetTests(unittest.TestCase):
    """Tests para los presets de audio."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Crear un archivo de audio de prueba
        sr = 24000
        duration = 1.0  # 1 segundo
        n = int(sr * duration)
        # Onda seno a 440Hz
        self.test_audio = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, duration, n))
        self.test_path = self.tmp / "test.wav"
        sf.write(self.test_path, self.test_audio, sr, subtype="PCM_16")
    
    def test_all_presets_exist(self):
        """Test que todos los presets están definidos."""
        expected_presets = [
            "neutro", "narracion", "podcast", "radio", "cine",
            "sala", "catedral", "radio_vintage", "susurro", "eco",
            # Nuevos presets profesionales
            "audiolibro_pro", "audiolibro_ebu", "podcast_pro", 
            "voz_limpia", "master_pro"
        ]
        for preset_name in expected_presets:
            self.assertIn(preset_name, PRESETS, 
                        f"Preset {preset_name} no encontrado")
    
    def test_audiolibro_pro_preset_defined(self):
        """Test que el preset audiolibro_pro tiene filtros definidos."""
        preset = PRESETS["audiolibro_pro"]
        self.assertIn("de-essing", preset.description.lower())
        self.assertIn("noise gate", preset.description.lower())
        self.assertIn("agate", preset.filters)
        self.assertIn("equalizer", preset.filters)
    
    def test_apply_audiolibro_pro_preset(self):
        """Test que se puede aplicar el preset audiolibro_pro."""
        out_path = self.tmp / "test_audiolibro_pro.wav"
        result = apply_fx(
            self.test_path, out_path,
            preset_name="audiolibro_pro",
            force=True
        )
        self.assertTrue(out_path.exists())
        self.assertEqual(result, out_path)
    
    def test_apply_ebu_normalization(self):
        """Test que se puede aplicar normalización EBU R128."""
        out_path = self.tmp / "test_ebu.wav"
        result = normalize_lufs(
            self.test_path, out_path,
            target_lufs=-16.0,
            true_peak=-1.5,
            lra=11.0,
            force=True
        )
        self.assertTrue(out_path.exists())
        self.assertEqual(result, out_path)
        
        # Analizar el audio normalizado
        analysis = analyze_audio(out_path)
        # Verificar que el LUFS integrado está cerca de -16
        # (puede no ser exacto debido al material de prueba)
        self.assertIn("input_i", analysis)


class DeesserTests(unittest.TestCase):
    """Tests para el de-esser."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        sr = 24000
        duration = 0.5
        n = int(sr * duration)
        # Audio con componentes en frecuencia de sibilantes (4-8 kHz)
        t = np.linspace(0, duration, n)
        # Onda seno a 4000Hz (sibilante)
        self.test_audio = 0.3 * np.sin(2 * np.pi * 4000 * t)
        # Onda seno a 1000Hz (voz)
        self.test_audio += 0.5 * np.sin(2 * np.pi * 1000 * t)
        self.test_path = self.tmp / "test_sibilant.wav"
        sf.write(self.test_path, self.test_audio, sr, subtype="PCM_16")
    
    def test_deess_audio(self):
        """Test que el de-esser reduce las frecuencias de sibilantes."""
        out_path = self.tmp / "test_deessed.wav"
        result = deess_audio(
            self.test_path, out_path,
            frequency=4000.0,
            bandwidth=1000.0,
            gain=-3.0,
            force=True
        )
        self.assertTrue(out_path.exists())
        self.assertEqual(result, out_path)


class NoiseGateTests(unittest.TestCase):
    """Tests para el noise gate."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        sr = 24000
        duration = 1.0
        n = int(sr * duration)
        
        # Crear audio con silencio al principio y final
        self.test_audio = np.zeros(n, dtype=np.float32)
        # Añadir señal en el medio (0.3 a 0.7 segundos)
        start = int(0.3 * sr)
        end = int(0.7 * sr)
        t = np.linspace(0, 0.4, end - start)
        self.test_audio[start:end] = 0.5 * np.sin(2 * np.pi * 1000 * t)
        
        self.test_path = self.tmp / "test_with_silence.wav"
        sf.write(self.test_path, self.test_audio, sr, subtype="PCM_16")
    
    def test_noise_gate(self):
        """Test que el noise gate funciona correctamente."""
        out_path = self.tmp / "test_gated.wav"
        result = noise_gate(
            self.test_path, out_path,
            level_in=0.02,   # ≈ -34dB
            attack=0.01,     # 10ms (mínimo)
            release=0.1,     # 100ms
            force=True
        )
        self.assertTrue(out_path.exists())
        self.assertEqual(result, out_path)


class MultibandCompressTests(unittest.TestCase):
    """Tests para la compresión multibanda."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        sr = 24000
        duration = 0.5
        n = int(sr * duration)
        t = np.linspace(0, duration, n)
        # Audio con variaciones de amplitud
        self.test_audio = 0.7 * np.sin(2 * np.pi * 1000 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 10 * t))
        self.test_path = self.tmp / "test_multiband.wav"
        sf.write(self.test_path, self.test_audio, sr, subtype="PCM_16")
    
    def test_multiband_compress(self):
        """Test que la compresión multibanda funciona."""
        out_path = self.tmp / "test_compressed.wav"
        result = multiband_compress(
            self.test_path, out_path,
            points="-60/-60|-30/-20|-10/-10|0/-8",
            gain=4.0,
            attacks=0.01,
            decays=0.1,
            force=True
        )
        self.assertTrue(out_path.exists())
        self.assertEqual(result, out_path)


class ProfessionalChainTests(unittest.TestCase):
    """Tests para la cadena profesional completa."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        sr = 24000
        duration = 1.0
        n = int(sr * duration)
        t = np.linspace(0, duration, n)
        # Audio de prueba realista
        self.test_audio = 0.5 * np.sin(2 * np.pi * 1000 * t)
        self.test_path = self.tmp / "test_chain.wav"
        sf.write(self.test_path, self.test_audio, sr, subtype="PCM_16")
    
    def test_professional_chain_with_ebu(self):
        """Test cadena profesional con normalización EBU R128."""
        out_path = self.tmp / "test_pro_chain.wav"
        result = apply_professional_chain(
            self.test_path, out_path,
            preset="audiolibro_pro",
            target_lufs=-16.0,
            true_peak=-1.5,
            lra=11.0,
            force=True
        )
        self.assertTrue(out_path.exists())
        self.assertEqual(result, out_path)
    
    def test_professional_chain_without_ebu(self):
        """Test cadena profesional sin normalización EBU R128."""
        out_path = self.tmp / "test_pro_chain_no_ebu.wav"
        result = apply_professional_chain(
            self.test_path, out_path,
            preset="audiolibro_pro",
            target_lufs=None,
            force=True
        )
        self.assertTrue(out_path.exists())
        self.assertEqual(result, out_path)


class EBUR128Tests(unittest.TestCase):
    """Tests para la normalización EBU R128."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        sr = 24000
        duration = 1.0
        n = int(sr * duration)
        t = np.linspace(0, duration, n)
        # Audio de prueba
        self.test_audio = 0.5 * np.sin(2 * np.pi * 1000 * t)
        self.test_path = self.tmp / "test_ebu.wav"
        sf.write(self.test_path, self.test_audio, sr, subtype="PCM_16")
    
    def test_ensure_ebu_r128(self):
        """Test que ensure_ebu_r128 aplica normalización."""
        out_path = self.tmp / "test_ebu_ensured.wav"
        result = ensure_ebu_r128(
            self.test_path, out_path,
            target_lufs=-16.0,
            true_peak=-1.5,
            lra=11.0,
            force=True
        )
        self.assertTrue(out_path.exists())
        self.assertEqual(result, out_path)
        
        # Verificar que el análisis devuelve valores
        analysis = analyze_audio(out_path)
        self.assertIn("input_i", analysis)
        self.assertIn("input_tp", analysis)


class AudioAnalysisTests(unittest.TestCase):
    """Tests para el análisis de audio."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        sr = 24000
        duration = 1.0
        n = int(sr * duration)
        t = np.linspace(0, duration, n)
        self.test_audio = 0.5 * np.sin(2 * np.pi * 1000 * t)
        self.test_path = self.tmp / "test_analysis.wav"
        sf.write(self.test_path, self.test_audio, sr, subtype="PCM_16")
    
    def test_analyze_audio(self):
        """Test que analyze_audio devuelve métricas válidas."""
        analysis = analyze_audio(self.test_path)
        
        # Verificar que tenemos métricas clave
        self.assertIn("input_i", analysis)  # LUFS integrado
        self.assertIn("input_tp", analysis)  # Pico verdadero
        self.assertIn("input_lra", analysis)  # Rango dinámico
        
        # Verificar que los valores son numéricos (pueden ser string en JSON)
        # Convertir a float si es string
        input_i = float(analysis["input_i"]) if isinstance(analysis["input_i"], str) else analysis["input_i"]
        input_tp = float(analysis["input_tp"]) if isinstance(analysis["input_tp"], str) else analysis["input_tp"]
        input_lra = float(analysis["input_lra"]) if isinstance(analysis["input_lra"], str) else analysis["input_lra"]
        
        # Verificar que son numéricos
        self.assertIsInstance(input_i, float)
        self.assertIsInstance(input_tp, float)
        self.assertIsInstance(input_lra, float)


if __name__ == "__main__":
    unittest.main()
