"""Hermetic pytest for ocr.py — no network, no model, engine mocked."""

import ocr
import pytest


@pytest.fixture(autouse=True)
def _reset_engine(monkeypatch):
    monkeypatch.setattr(ocr, "_engine", None)
    monkeypatch.setattr(ocr, "_engine_failed", False)


def test_dedup_merges_jitter_and_bridges_dropout():
    frames = [
        ("hello world", 0.9),
        ("hello wor1d", 0.95),  # l<->1 jitter, higher conf
        ("", 0.0),  # 1-frame dropout -> bridged
        ("hello world", 0.85),
        ("something else", 0.9),
        ("something else", 0.9),
    ]
    spans = ocr.dedup_spans(frames, fps=1.0)
    assert len(spans) == 2
    assert spans[0]["text"] == "hello wor1d"  # max-conf wins
    assert (spans[0]["start"], spans[0]["end"]) == (0.0, 4.0)
    assert (spans[1]["start"], spans[1]["end"]) == (4.0, 6.0)


def test_dedup_gap_over_bridge_splits():
    frames = [("a b c d", 0.9), ("", 0.0), ("", 0.0), ("a b c d", 0.9)]
    assert len(ocr.dedup_spans(frames, fps=1.0)) == 2


def test_dedup_empty():
    assert ocr.dedup_spans([], fps=1.0) == []
    assert ocr.dedup_spans([("", 0.0)] * 3, fps=1.0) == []


def test_engine_absent_returns_empty(monkeypatch):
    monkeypatch.setattr(ocr, "_get_engine", lambda: None)
    assert ocr.ocr_frames("frames", ["f1.jpg"], 1.0) == ("", [])


def test_fps_zero_guard(monkeypatch):
    """fps=0 is a free float on /analyze — must not ZeroDivisionError."""

    class Fake:
        def __call__(self, path):
            return [[None, "text", 0.9]], None

    monkeypatch.setattr(ocr, "_get_engine", lambda: Fake())
    text, segs = ocr.ocr_frames("frames", ["f1.jpg"], 0)
    assert text == "text"
    assert segs == [{"start": 0.0, "end": 1.0, "text": "text", "confidence": 0.9}]


def test_full_chain_with_mocked_engine(monkeypatch):
    outputs = {
        "f1.jpg": [[None, "hello", 0.9]],
        "f2.jpg": [[None, "hello", 0.95]],
        "f3.jpg": [[None, "bye", 0.8], [None, "now", 0.9]],
    }

    class Fake:
        def __call__(self, path):
            from pathlib import Path

            return outputs.get(Path(path).name), None

    monkeypatch.setattr(ocr, "_get_engine", lambda: Fake())
    text, segs = ocr.ocr_frames("frames", ["f1.jpg", "f2.jpg", "f3.jpg"], 1.0)
    assert text == "hello\nbye now"
    assert [s["text"] for s in segs] == ["hello", "bye now"]
    assert segs[1]["confidence"] == pytest.approx(0.85)  # mean of regions


def test_read_frame_error_is_survived(monkeypatch):
    class Boom:
        def __call__(self, path):
            raise RuntimeError("corrupt jpg")

    monkeypatch.setattr(ocr, "_get_engine", lambda: Boom())
    assert ocr.ocr_frames("frames", ["f1.jpg"], 1.0) == ("", [])


def test_job_response_surfaces_overlay_fields():
    """Load-bearing claim: JobResponse exposes overlay_* when present, None sinon.
    main.py needs R2 env at import -> stub it."""
    import os

    os.environ.setdefault("R2_ENDPOINT", "https://test.invalid")
    for k in ("R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        os.environ.setdefault(k, "test")
    pytest.importorskip("faster_whisper")
    pytest.importorskip("yt_dlp")
    from main import JobResponse

    base = {"job_id": "x", "status": "done"}
    r = JobResponse(
        **{**base, "overlay_text": "t", "overlay_segments": [{"text": "t"}]}
    )
    assert r.overlay_text == "t"
    assert r.overlay_segments == [{"text": "t"}]
    r2 = JobResponse(**base)
    assert r2.overlay_text is None
    assert r2.overlay_segments is None


def test_job_response_surfaces_voice_field():
    """Load-bearing claim: JobResponse exposes `voice` when present, None sinon."""
    import os

    os.environ.setdefault("R2_ENDPOINT", "https://test.invalid")
    for k in ("R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        os.environ.setdefault(k, "test")
    pytest.importorskip("faster_whisper")
    pytest.importorskip("yt_dlp")
    from main import JobResponse

    base = {"job_id": "x", "status": "done"}
    voice_payload = {
        "global": {
            "f0_mean_hz": 180.0,
            "f0_std_hz": 10.0,
            "gender": "female",
            "speech_rate_wps": 2.1,
        },
        "hook": {
            "f0_mean_hz": 200.0,
            "f0_std_hz": 12.0,
            "gender": "female",
            "speech_rate_wps": 3.0,
        },
    }
    r = JobResponse(**{**base, "voice": voice_payload})
    assert r.voice == voice_payload
    r2 = JobResponse(**base)
    assert r2.voice is None
