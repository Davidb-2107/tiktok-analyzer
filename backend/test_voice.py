"""Hermetic pytest for voice.py — librosa.load/pyin mocked, no real audio."""

import numpy as np
import pytest

import voice


def test_gender_heuristic_thresholds():
    assert voice._gender(120.0) == "male"
    assert voice._gender(164.999) == "male"
    assert voice._gender(165.0) == "female"
    assert voice._gender(220.0) == "female"
    assert voice._gender(None) is None


def test_speech_rate_counts_words_in_window():
    segments = [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "hello there friend",
            "words": [
                {"start": 0.1, "end": 0.4, "word": "hello"},
                {"start": 0.5, "end": 0.9, "word": "there"},
                {"start": 1.0, "end": 1.4, "word": "friend"},
            ],
        },
        {
            "start": 4.0,
            "end": 4.5,
            "text": "late",
            "words": [{"start": 4.0, "end": 4.5, "word": "late"}],
        },
    ]
    # window [0, 2): 3 words / 2s
    assert voice._speech_rate_wps(segments, 0.0, 2.0) == pytest.approx(1.5)
    # window [0, 5): all 4 words / 5s
    assert voice._speech_rate_wps(segments, 0.0, 5.0) == pytest.approx(0.8)


def test_speech_rate_none_without_word_timing():
    segments = [{"start": 0.0, "end": 2.0, "text": "hello there"}]  # no "words" key
    assert voice._speech_rate_wps(segments, 0.0, 2.0) is None


def test_speech_rate_none_when_window_has_no_words():
    segments = [
        {
            "start": 10.0,
            "end": 10.5,
            "words": [{"start": 10.0, "end": 10.5, "word": "x"}],
        }
    ]
    assert voice._speech_rate_wps(segments, 0.0, 2.0) is None


def test_analyze_voice_returns_none_on_load_failure(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("corrupt file")

    monkeypatch.setattr(voice.librosa, "load", boom)
    assert voice.analyze_voice("bad.mp3", [], 10.0, 5.0) is None


def test_analyze_voice_returns_none_on_empty_audio(monkeypatch):
    monkeypatch.setattr(voice.librosa, "load", lambda *a, **kw: (np.array([]), 16000))
    assert voice.analyze_voice("empty.mp3", [], 10.0, 5.0) is None


def test_analyze_voice_wires_global_and_hook(monkeypatch):
    sr = 16000
    y = np.zeros(sr * 10, dtype=np.float32)  # 10s of silence
    monkeypatch.setattr(voice.librosa, "load", lambda *a, **kw: (y, sr))

    def fake_pyin(y_slice, fmin, fmax, sr):
        n = len(y_slice)
        f0 = np.full(n, 150.0)
        voiced_flag = np.ones(n, dtype=bool)
        return f0, voiced_flag, np.ones(n)

    monkeypatch.setattr(voice.librosa, "pyin", fake_pyin)

    segments = [
        {
            "start": 0.0,
            "end": 1.0,
            "words": [{"start": 0.2, "end": 0.5, "word": "hi"}],
        }
    ]
    result = voice.analyze_voice("clip.mp3", segments, duration=10.0, hook_window_s=5.0)
    assert result["global"]["f0_mean_hz"] == pytest.approx(150.0)
    assert result["global"]["gender"] == "male"
    assert result["hook"]["f0_mean_hz"] == pytest.approx(150.0)
    # 1 word in [0, 5) -> 1/5 wps; same word also falls in [0, 10)
    assert result["hook"]["speech_rate_wps"] == pytest.approx(0.2)
    assert result["global"]["speech_rate_wps"] == pytest.approx(0.1)


def test_analyze_voice_hook_window_capped_by_duration():
    """hook_window_s (5s) longer than duration (2s) must not slice past the
    clip end."""
    sr = 16000
    y = np.zeros(sr * 2, dtype=np.float32)

    import voice as voice_mod

    def fake_load(*a, **kw):
        return y, sr

    def fake_pyin(y_slice, fmin, fmax, sr):
        n = len(y_slice)
        return np.full(n, 150.0), np.ones(n, dtype=bool), np.ones(n)

    voice_mod.librosa.load = fake_load
    voice_mod.librosa.pyin = fake_pyin
    result = voice_mod.analyze_voice("clip.mp3", [], duration=2.0, hook_window_s=5.0)
    assert result["global"] == result["hook"]
