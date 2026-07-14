# Voice/Prosody Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `voice` field to the job payload carrying pitch (F0), a gender heuristic, and speech rate — computed globally and over the existing hook window — using `librosa`.

**Architecture:** A new hermetic module `backend/voice.py` (mirrors the existing `backend/ocr.py` pattern) exposes one pure function, `analyze_voice(audio_path, segments, duration, hook_window_s) -> dict | None`. `backend/main.py` calls it via `asyncio.to_thread` alongside the existing OCR fan-out, in both processing branches, and threads the result into the terminal `_update_job(...)` call and `JobResponse` model.

**Tech Stack:** Python, librosa (new dependency), numpy (already a librosa transitive dep), pytest (existing test runner), FastAPI/Pydantic (existing).

## Global Constraints

- `voice` is `null` whenever `transcribe=False` (no audio was ever extracted) — same gating as `transcript`/`segments`.
- `speech_rate_wps` is `null` whenever no word-level segments are available (source had native captions, so Whisper never ran) — per spec, no fallback estimation.
- `gender` is a heuristic F0 threshold (165 Hz), not a trained classifier — must be documented as such in code.
- Any failure inside voice analysis (corrupt audio, empty file, DSP error) must degrade to `voice: null` and never raise past the pipeline — mirrors `ocr_frames`' own internal error swallowing (see `backend/test_ocr.py::test_read_frame_error_is_survived`).
- Hook window reuses the existing `HOOK_WINDOW_S` env var (default 5s) — no new env var for the hook boundary.
- No new job status. No per-word/per-segment granularity. No ML gender classifier. No RMS/energy or jitter/shimmer/HNR metrics (out of scope per spec).

---

### Task 1: `backend/voice.py` — pitch, gender, speech-rate helpers

**Files:**
- Modify: `backend/requirements.txt` (add `librosa`)
- Create: `backend/voice.py`
- Create: `backend/test_voice.py`

**Interfaces:**
- Produces: `voice.analyze_voice(audio_path: pathlib.Path, segments: list[dict], duration: float, hook_window_s: float) -> dict | None`
  - Returns `None` on any failure (unreadable/empty audio).
  - On success: `{"global": {...}, "hook": {...}}` where each window dict is `{"f0_mean_hz": float | None, "f0_std_hz": float | None, "gender": "male" | "female" | None, "speech_rate_wps": float | None}`.
  - `segments` is the same list-of-dicts shape `_transcribe`/Whisper already produces: `[{"start": float, "end": float, "text": str, "words": [{"start": float, "end": float, "word": str}, ...]}, ...]` (the `"words"` key is absent/empty when the caller has no word timing).

- [ ] **Step 1: Add the dependency**

Append to `backend/requirements.txt`:
```
librosa==0.10.2.post1
```

- [ ] **Step 2: Write the failing tests for the pure helpers (no audio I/O)**

Create `backend/test_voice.py`:
```python
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
        {"start": 10.0, "end": 10.5, "words": [{"start": 10.0, "end": 10.5, "word": "x"}]}
    ]
    assert voice._speech_rate_wps(segments, 0.0, 2.0) is None
```

- [ ] **Step 3: Run tests to verify they fail (voice.py doesn't exist yet)**

Run: `cd backend && python -m pytest test_voice.py -v`
Expected: `ModuleNotFoundError: No module named 'voice'` (collection error)

- [ ] **Step 4: Implement `backend/voice.py`**

```python
"""Prosody analysis over extracted audio: pitch (F0), a gender heuristic,
and speech rate, computed over the full clip and over the hook window.
Hermetic wrt the rest of the pipeline — librosa does the DSP, this module
is the aggregation + the two windows."""

from pathlib import Path

import librosa
import numpy as np

# 165Hz: standard midpoint between typical male (~85-180Hz) and female
# (~165-255Hz) speaking fundamental frequency ranges. A threshold heuristic,
# not a trained classifier — atypical voices (deep female, high male) will
# misclassify.
GENDER_F0_THRESHOLD_HZ = 165.0

# pyin search bounds: below typical male F0 floor / above typical female
# F0 ceiling, wide enough to avoid clipping real voices.
FMIN_HZ = 65.0
FMAX_HZ = 400.0


def _gender(f0_mean_hz: float | None) -> str | None:
    if f0_mean_hz is None:
        return None
    return "male" if f0_mean_hz < GENDER_F0_THRESHOLD_HZ else "female"


def _speech_rate_wps(
    segments: list[dict], start_s: float, end_s: float
) -> float | None:
    """Words per second inside [start_s, end_s), counted from word-level
    Whisper segments. None if no word timing exists (caption-sourced
    transcripts carry no `words` field) or the window contains no words."""
    words = 0
    for seg in segments:
        for w in seg.get("words") or []:
            if start_s <= w["start"] < end_s:
                words += 1
    span = end_s - start_s
    if words == 0 or span <= 0:
        return None
    return words / span


def _pitch_stats(y: np.ndarray, sr: int) -> tuple[float | None, float | None]:
    """Mean/std F0 (Hz) over voiced frames. (None, None) if no voiced frames
    (silence, pure noise, empty slice)."""
    if y.size == 0:
        return None, None
    f0, voiced_flag, _voiced_prob = librosa.pyin(
        y, fmin=FMIN_HZ, fmax=FMAX_HZ, sr=sr
    )
    voiced = f0[voiced_flag] if voiced_flag is not None else f0
    voiced = voiced[~np.isnan(voiced)]
    if voiced.size == 0:
        return None, None
    return float(np.mean(voiced)), float(np.std(voiced))


def _window_metrics(
    y: np.ndarray, sr: int, segments: list[dict], start_s: float, end_s: float
) -> dict:
    start_sample = int(start_s * sr)
    end_sample = int(end_s * sr)
    f0_mean, f0_std = _pitch_stats(y[start_sample:end_sample], sr)
    return {
        "f0_mean_hz": f0_mean,
        "f0_std_hz": f0_std,
        "gender": _gender(f0_mean),
        "speech_rate_wps": _speech_rate_wps(segments, start_s, end_s),
    }


def analyze_voice(
    audio_path: Path,
    segments: list[dict],
    duration: float,
    hook_window_s: float,
) -> dict | None:
    """Global + hook-window prosody metrics. Returns None on any failure
    (corrupt/empty audio, DSP error) — callers must never let this sink a
    job, matching ocr_frames' own error-swallowing posture."""
    try:
        y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    except Exception:
        return None
    if y.size == 0:
        return None
    full_end = duration if duration else y.size / sr
    hook_end = min(hook_window_s, full_end)
    return {
        "global": _window_metrics(y, sr, segments, 0.0, full_end),
        "hook": _window_metrics(y, sr, segments, 0.0, hook_end),
    }
```

- [ ] **Step 5: Run tests to verify the pure-helper tests pass**

Run: `cd backend && python -m pytest test_voice.py -v`
Expected: 4 tests PASS (the pure-logic tests don't touch `librosa.load`/`pyin`)

- [ ] **Step 6: Add mocked-DSP tests for `analyze_voice` itself**

Append to `backend/test_voice.py`:
```python
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
```

- [ ] **Step 7: Run all voice tests to verify they pass**

Run: `cd backend && python -m pytest test_voice.py -v`
Expected: 8 tests PASS

- [ ] **Step 8: Install the new dependency locally and re-run full suite**

Run: `cd backend && pip install -r requirements.txt && python -m pytest test_voice.py -v`
Expected: 8 tests PASS with real `librosa` installed (import works, mocks still applied per-test via monkeypatch)

- [ ] **Step 9: Commit**

```bash
git add backend/requirements.txt backend/voice.py backend/test_voice.py
git commit -m "feat: add voice.py — pitch/gender/speech-rate prosody analysis"
```

---

### Task 2: Wire `voice.analyze_voice` into the job pipeline

**Files:**
- Modify: `backend/main.py`
  - Import: add `import voice` near the top (alongside other local module imports like `ocr`)
  - `JobResponse` class (~line 402-414): add `voice: dict | None = None`
  - Processing branches (~lines 813-867): call `voice.analyze_voice` in both branches, pass result into the terminal `_update_job(...)` call
- Test: `backend/test_ocr.py` (add a `JobResponse` exposure test alongside the existing `test_job_response_surfaces_overlay_fields`, same pattern)

**Interfaces:**
- Consumes: `voice.analyze_voice(audio_path: Path, segments: list[dict], duration: float, hook_window_s: float) -> dict | None` (Task 1)
- Consumes: existing `HOOK_WINDOW_S` module-level constant (`backend/main.py:148`)
- Consumes: existing `audio_path` variable (from `_audio_path(job_id)`, `backend/main.py:748`) and `duration` (from `_download_video`, `backend/main.py:744`)

- [ ] **Step 1: Write the failing `JobResponse` test**

Append to `backend/test_ocr.py` (it already sets up the `main` import guards):
```python
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
        "global": {"f0_mean_hz": 180.0, "f0_std_hz": 10.0, "gender": "female", "speech_rate_wps": 2.1},
        "hook": {"f0_mean_hz": 200.0, "f0_std_hz": 12.0, "gender": "female", "speech_rate_wps": 3.0},
    }
    r = JobResponse(**{**base, "voice": voice_payload})
    assert r.voice == voice_payload
    r2 = JobResponse(**base)
    assert r2.voice is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest test_ocr.py::test_job_response_surfaces_voice_field -v`
Expected: FAIL with `ValidationError` / `extra fields not permitted` (or similar) — `voice` isn't a declared field yet

- [ ] **Step 3: Add the `voice` field to `JobResponse`**

In `backend/main.py`, modify the `JobResponse` class (~line 402-414):
```python
class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    frames: list[str] = []
    error: str | None = None
    url: str | None = None
    transcript: str | None = None
    duration: float | None = None
    segments: list[dict] | None = None
    overlay_text: str | None = None
    overlay_segments: list[dict] | None = None
    hook_overlay_text: str | None = None
    hook_overlay_segments: list[dict] | None = None
    voice: dict | None = None
    project: str | None = None
    user_tags: list[str] = []
    fps: float | None = None
    start_s: float | None = None
    end_s: float | None = None
    # Consumed by JobHistory.jsx (timestamps + @handle search) — /jobs now
    # whitelists through this model, so absent fields here vanish from the UI.
    created_at: str | None = None
    author: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_ocr.py::test_job_response_surfaces_voice_field -v`
Expected: PASS

- [ ] **Step 5: Import `voice` in `backend/main.py`**

Find the existing `import ocr` (or equivalent local-module import) near the top of `backend/main.py` and add directly after it:
```python
import voice
```

- [ ] **Step 6: Wire the captions-found branch (no Whisper run)**

In `backend/main.py`, the captions-found branch currently reads (~line 821-834):
```python
        segments: list[dict] = []
        if transcript or not transcribe:
            (
                r2_keys,
                (
                    (overlay_text, overlay_segments),
                    (hook_overlay_text, hook_overlay_segments),
                ),
            ) = await asyncio.gather(
                asyncio.to_thread(_upload_frames, job_id, frame_names),
                asyncio.to_thread(
                    _ocr_main_and_hook, job_id, frame_names, fps, hook_frame_names
                ),
            )
```

Replace with (adds a third gather leg, only when transcribing — `transcribe=False` jobs must not touch `audio_path`, which was never extracted):
```python
        segments: list[dict] = []
        if transcript or not transcribe:
            gather_tasks = [
                asyncio.to_thread(_upload_frames, job_id, frame_names),
                asyncio.to_thread(
                    _ocr_main_and_hook, job_id, frame_names, fps, hook_frame_names
                ),
            ]
            if transcribe:
                gather_tasks.append(
                    asyncio.to_thread(
                        voice.analyze_voice, audio_path, segments, duration, HOOK_WINDOW_S
                    )
                )
            gather_results = await asyncio.gather(*gather_tasks)
            r2_keys, (
                (overlay_text, overlay_segments),
                (hook_overlay_text, hook_overlay_segments),
            ) = gather_results[0], gather_results[1]
            voice_metrics = gather_results[2] if transcribe else None
```

- [ ] **Step 7: Wire the Whisper branch**

Immediately below, the `else` branch currently reads (~line 835-850):
```python
        else:
            # No captions: frames still local. Mark transcribing so the UI shows
            # progress, then fan out upload + Whisper concurrently.
            _update_job(job_id, status="transcribing", frames=frame_names)
            r2_keys, transcribe_result, ocr_result = await asyncio.gather(
                asyncio.to_thread(_upload_frames, job_id, frame_names),
                asyncio.to_thread(_transcribe, audio_path),
                asyncio.to_thread(
                    _ocr_main_and_hook, job_id, frame_names, fps, hook_frame_names
                ),
            )
            transcript, segments = transcribe_result
            (
                (overlay_text, overlay_segments),
                (hook_overlay_text, hook_overlay_segments),
            ) = ocr_result
```

Note this branch only runs when `transcribe=True` (it's the `else` of `if transcript or not transcribe`, and reaching `else` with `not transcribe` false means `transcribe` is true) — `voice.analyze_voice` always runs here, but needs `segments` from the just-completed `_transcribe` call first, so it can't join the same `asyncio.gather` (it depends on that gather's output). Replace with:
```python
        else:
            # No captions: frames still local. Mark transcribing so the UI shows
            # progress, then fan out upload + Whisper concurrently.
            _update_job(job_id, status="transcribing", frames=frame_names)
            r2_keys, transcribe_result, ocr_result = await asyncio.gather(
                asyncio.to_thread(_upload_frames, job_id, frame_names),
                asyncio.to_thread(_transcribe, audio_path),
                asyncio.to_thread(
                    _ocr_main_and_hook, job_id, frame_names, fps, hook_frame_names
                ),
            )
            transcript, segments = transcribe_result
            (
                (overlay_text, overlay_segments),
                (hook_overlay_text, hook_overlay_segments),
            ) = ocr_result
            voice_metrics = await asyncio.to_thread(
                voice.analyze_voice, audio_path, segments, duration, HOOK_WINDOW_S
            )
```

- [ ] **Step 8: Pass `voice_metrics` into the terminal `_update_job` call**

The terminal call currently reads (~line 857-867):
```python
        _update_job(
            job_id,
            status="done",
            frames=r2_keys,
            transcript=transcript,
            segments=segments,
            overlay_text=overlay_text or None,
            overlay_segments=overlay_segments or None,
            hook_overlay_text=hook_overlay_text or None,
            hook_overlay_segments=hook_overlay_segments or None,
        )
```

Add `voice=voice_metrics`:
```python
        _update_job(
            job_id,
            status="done",
            frames=r2_keys,
            transcript=transcript,
            segments=segments,
            overlay_text=overlay_text or None,
            overlay_segments=overlay_segments or None,
            hook_overlay_text=hook_overlay_text or None,
            hook_overlay_segments=hook_overlay_segments or None,
            voice=voice_metrics,
        )
```

- [ ] **Step 9: Guard `voice_metrics` for the `transcribe=False` path**

Since `voice_metrics` is only assigned inside the `if transcribe:` sub-branch (Step 6) and the `else` branch (Step 7, always `transcribe=True`), add a default before the `if transcript or not transcribe:` block (~just above line 821) so `transcribe=False` jobs don't hit an `UnboundLocalError`:
```python
        segments: list[dict] = []
        voice_metrics: dict | None = None
        if transcript or not transcribe:
```
(This replaces the bare `segments: list[dict] = []` line from Step 6 with both declarations.)

- [ ] **Step 10: Run the full backend test suite**

Run: `cd backend && python -m pytest -v`
Expected: all tests PASS, including the new `test_job_response_surfaces_voice_field` and all of `test_voice.py`

- [ ] **Step 11: Manual smoke test against a real short video**

Run the backend locally (`cd backend && uvicorn main:app --reload`), then:
```bash
curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" -d '{"url":"<a short tiktok/youtube url>","fps":1}'
```
Poll `GET /status/{job_id}` until `status=="done"`. Confirm the response includes a `voice` object shaped `{"global": {...}, "hook": {...}}` with non-null `f0_mean_hz`/`gender` (and non-null `speech_rate_wps` if the source had no native captions).

- [ ] **Step 12: Commit**

```bash
git add backend/main.py backend/test_ocr.py
git commit -m "feat: wire voice.analyze_voice into the job pipeline and JobResponse"
```

## Self-Review

**Spec coverage:**
- `voice` field shape (`global`/`hook`, `f0_mean_hz`/`f0_std_hz`/`gender`/`speech_rate_wps`) → Task 1 Step 4, Task 2 Step 3.
- `voice: null` when `transcribe=False` → Task 2 Step 9 (default `None`, never overwritten on that path).
- `speech_rate_wps: null` without word timing → Task 1 `_speech_rate_wps` + `test_speech_rate_none_without_word_timing`.
- Hook window reuses `HOOK_WINDOW_S` → Task 2 Steps 6-7 pass the module constant through.
- Gender heuristic documented as approximation → Task 1 Step 4 docstring/comment.
- Failure → `voice: null`, never sinks the job → Task 1 `analyze_voice` try/except returning `None`; Task 2 calls it via `asyncio.to_thread` with no additional try/except needed since the module already swallows.
- `librosa` dependency, no Docker changes → Task 1 Step 1.
- Out-of-scope items (new job status, per-word granularity, ML gender classifier, RMS/timbre) → not introduced anywhere in this plan.

**Placeholder scan:** none found — every step has complete code or an exact command with expected output.

**Type consistency:** `analyze_voice(audio_path, segments, duration, hook_window_s) -> dict | None` signature matches across Task 1 (definition + tests) and Task 2 (call sites). `voice: dict | None` matches between `JobResponse` and the `_update_job(..., voice=voice_metrics)` call.
