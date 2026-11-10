"""Pruebas sin XTTS: usan un motor simulado, así que corren en segundos y sin descargas."""
from __future__ import annotations

import threading

import numpy as np
import pytest
import soundfile as sf

from voxforge.config import Settings
from voxforge.db import Store
from voxforge.engines.base import TTSEngine
from voxforge.pipeline import narrate, fragment_hash, speech_rate_ok
from voxforge.utils import SynthCancelledError


class FakeEngine(TTSEngine):
    """Motor de prueba: genera ruido determinista con duración ~10 car/s."""

    name = "fake"
    sample_rate = 24000
    MODEL = "fake-v1"

    def __init__(self, sample_rate: int = 24000):
        self._sr = sample_rate
        self.loads = 0
        self.synth_calls = 0

    def load(self) -> None:
        self.loads += 1

    def unload(self) -> None:
        pass

    def get_latents(self, speaker_wav):
        """Stub compatible con el pipeline: devuelve la tupla de latentes."""
        return ("fake_cond", "fake_emb")

    def synthesize(self, text, reference_wav=None, language="es", seed=0,
                   latentes=None, **generation_params):
        self.synth_calls += 1
        n = max(int(len(text) / 10.0 * self._sr), self._sr // 4)
        rng = np.random.default_rng(seed)
        return (rng.standard_normal(n) * 0.05).astype(np.float32)


@pytest.fixture
def settings():
    s = Settings()
    s.thermal_guard = False  # sin pausas térmicas al correr los tests
    return s


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "test.db")


@pytest.fixture
def profile(store, tmp_path):
    ref = tmp_path / "ref.wav"
    sr = 24000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    wav = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(ref), wav, sr)
    store.add_profile("fake_voice", ref, "abc123", "es")
    return store.get_profile("fake_voice")


def test_fragment_hash_stable():
    h1 = fragment_hash("fake", "abc", "es", "Hola mundo")
    h2 = fragment_hash("fake", "abc", "es", "Hola mundo")
    assert h1 == h2
    h3 = fragment_hash("fake", "abc", "es", "Hola Mundo")  # normaliza case
    assert h1 == h3
    h4 = fragment_hash("fake", "xyz", "es", "Hola mundo")
    assert h1 != h4


def test_speech_rate_ok(settings):
    assert speech_rate_ok("hola", 0.5, settings) is True  # texto corto
    assert speech_rate_ok("x" * 100, 10.0, settings) is True  # 10 cps
    assert speech_rate_ok("x" * 100, 1.0, settings) is False  # demasiado rápido
    assert speech_rate_ok("x" * 100, 30.0, settings) is False  # demasiado lento


def test_narrate_basic(settings, store, profile, tmp_path):
    engine = FakeEngine()
    cache = tmp_path / "cache"
    cache.mkdir()
    out = tmp_path / "out.wav"
    text = "Esto es una prueba corta de narración."
    result = narrate(text, profile, engine, store, settings, cache, out,
                     language="es", log=lambda _m: None)
    assert out.exists()
    assert result.fragments >= 1
    assert result.generated == result.fragments
    assert result.doubtful == 0
    assert engine.loads >= 1
    assert engine.synth_calls >= 1


def test_narrate_cache_hit(settings, store, profile, tmp_path):
    engine = FakeEngine()
    cache = tmp_path / "cache"
    cache.mkdir()
    out1 = tmp_path / "out1.wav"
    out2 = tmp_path / "out2.wav"
    text = "Frase uno. Frase dos."
    narrate(text, profile, engine, store, settings, cache, out1,
            language="es", log=lambda _m: None)
    calls_after_first = engine.synth_calls
    loads_after_first = engine.loads

    result = narrate(text, profile, engine, store, settings, cache, out2,
                     language="es", log=lambda _m: None)
    # con caché no se resintetiza nada
    assert engine.synth_calls == calls_after_first
    assert engine.loads >= loads_after_first
    assert result.cached == result.fragments
    assert result.generated == 0


def test_narrate_cancel(settings, store, profile, tmp_path):
    engine = FakeEngine()
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(SynthCancelledError):
        narrate("Este texto no debería sintetizarse porque ya está cancelado.",
                profile, engine, store, settings, tmp_path / "cache",
                tmp_path / "out.wav", language="es",
                cancel_event=cancel, log=lambda _m: None)


def test_resume_progress(settings, store, profile, tmp_path):
    engine = FakeEngine()
    cache = tmp_path / "cache"
    cache.mkdir()
    out = tmp_path / "out.wav"
    text = "Primera frase. Segunda frase más larga para forzar varios fragmentos."
    settings.max_chunk_chars = 20
    # simular una ejecución interrumpida tras el fragmento 1
    store.update_project_progress("p", 1, total_fragments=0,
                                  processed_fragments=0, current_fragment=1,
                                  status="running")
    r = narrate(text, profile, engine, store, settings, cache, out,
                language="es", project_name="p", chapter_id=1,
                log=lambda _m: None)
    assert r.fragments >= 2
    assert out.exists()
    prog = store.get_project_progress("p", 1)
    assert prog["status"] == "completed"
    assert prog["processed_fragments"] >= r.fragments
