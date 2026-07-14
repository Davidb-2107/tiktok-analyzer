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
    f0, voiced_flag, _voiced_prob = librosa.pyin(y, fmin=FMIN_HZ, fmax=FMAX_HZ, sr=sr)
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
