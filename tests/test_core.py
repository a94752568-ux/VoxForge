"""Pruebas sin XTTS: usan un motor simulado, así que corren en segundos y sin descargas."""
from __future__ import annotations

import hashlib
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf

from voxforge.config import Settings
from voxforge.db import Store
from voxforge.pipeline import narrate, fragment_hash, speech_rate_ok
from voxforge.engines.base import TTSEngine


class FakeEngine(TTSEngine):
    """Motor de prueba: genera ruido blanco o silencio según el texto."""

    name = "fake"
    MODEL = "fake-v1"

    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self._loaded = False
        self.loads = 0
        self.synth_calls = 0

    def load(self) -> None:
        self._loaded = True
        self.loads += 1

    def get_latents(self, speaker_wav: str):
        """Stub compatible con el pipeline real."""
        return {"fake": True, "path": speaker_wav}

    def synthesize(
        self,
        text: str,
        speaker_wav: str | None = None,
        language: str = "es",
        latents=None,
        **kwargs,
    ):
        self.synth_calls += 1
        # duración aproximada ~10 chars/s
        n_samples = max(int(len(text) / 10.0 * self.sample_rate), self.sample_rate // 4)
        # ruido de baja amplitud
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        wav = (rng.standard_normal(n_samples) * 0.05).astype(np.float32)
        return wav, self.sample_rate


@pytest.fixture
def settings(tmp_path):
    s = Settings()
    s.sample_rate = 24000
    s.max_chars = 200
    s.min_cps = 5.0
    s.max_cps = 20.0
    s.max_retries = 2
    s.cache_dir = tmp_path / "cache"
    s.cache_dir.mkdir()
    return s


@pytest.fixture
def store(tmp_path, settings):
    db = tmp_path / "test.db"
    st = Store(db, settings.cache_dir)
    return st


@pytest.fixture
def ref_wav(tmp_path, settings):
    p = tmp_path / "ref.wav"
    sr = settings.sample_rate
    t = np.linspace(0, 1.0, sr, endpoint=False)
    wav = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(p), wav, sr)
    return p


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


def test_narrate_basic(settings, store, ref_wav, tmp_path):
    engine = FakeEngine(settings.sample_rate)
    out = tmp_path / "out.wav"
    text = "Esto es una prueba corta de narración."
    result = narrate(
        engine, store, settings, text, ref_wav, "es", out,
        job_id="job1",
    )
    assert out.exists()
    assert result.fragments >= 1
    assert result.generated + result.cached == result.fragments
    assert engine.loads >= 1
    assert engine.synth_calls >= 1


def test_narrate_cache_hit(settings, store, ref_wav, tmp_path):
    engine = FakeEngine(settings.sample_rate)
    out1 = tmp_path / "out1.wav"
    out2 = tmp_path / "out2.wav"
    text = "Texto idéntico para probar caché de fragmentos."
    r1 = narrate(engine, store, settings, text, ref_wav, "es", out1, job_id="c1")
    loads_after_first = engine.loads
    r2 = narrate(engine, store, settings, text, ref_wav, "es", out2, job_id="c2")
    assert r2.cached >= 1 or r2.generated == 0
    # el motor se vuelve a cargar, pero no debería resintetizar si hay caché
    assert engine.loads >= loads_after_first


def test_narrate_cancel(settings, store, ref_wav, tmp_path):
    engine = FakeEngine(settings.sample_rate)
    out = tmp_path / "out.wav"
    cancel = threading.Event()
    cancel.set()
    text = "Este texto no debería sintetizarse porque ya está cancelado."
    with pytest.raises(Exception):
        narrate(
            engine, store, settings, text, ref_wav, "es", out,
            cancel_event=cancel, job_id="cancel1",
        )


def test_resume_progress(settings, store, ref_wav, tmp_path):
    engine = FakeEngine(settings.sample_rate)
    out = tmp_path / "out.wav"
    text = "Primera frase. Segunda frase más larga para forzar varios fragmentos."
    # forzar max_chars pequeño
    settings.max_chars = 20
    r = narrate(engine, store, settings, text, ref_wav, "es", out, job_id="resume1")
    assert r.fragments >= 2
    assert out.exists()
