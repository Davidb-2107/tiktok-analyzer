# Voice/Prosody Analysis — Design

## Goal

The pipeline already transcribes narration text (faster-whisper, word-level
timing) but extracts nothing about *how* it's spoken — pitch, speech rate,
voice gender. This adds a lightweight prosody analysis step so the job
payload carries those signals. Downstream use (format-card enrichment,
viral scoring, EL narration coaching) is intentionally undecided — this
spec only lays the metrics brick.

## Scope

New `voice` field on the job payload, populated only when `transcribe=True`
and audio was extracted (mirrors `transcript`/`segments` gating). For
`transcribe=False` jobs, `voice` is `null`.

```json
"voice": {
  "global": {
    "f0_mean_hz": 187.3,
    "f0_std_hz": 34.1,
    "gender": "female",
    "speech_rate_wps": 2.4
  },
  "hook": {
    "f0_mean_hz": 210.5,
    "f0_std_hz": 41.2,
    "gender": "female",
    "speech_rate_wps": 3.1
  }
}
```

`hook` covers `[0, HOOK_WINDOW_S]` seconds — same window/env var already
used by the OCR hook-microscope pass, for consistency.

## Metrics (v1)

- **`f0_mean_hz` / `f0_std_hz`** — pitch mean and standard deviation via
  `librosa.pyin` on the mono-downmixed audio track.
- **`gender`** — heuristic threshold on `f0_mean_hz`: `<165Hz` → `"male"`,
  `>=165Hz` → `"female"`. Documented as an approximation (not a trained
  classifier) — atypical voices (deep female, high male) will misclassify.
- **`speech_rate_wps`** — word count / elapsed time, derived from the
  word-level `segments` faster-whisper already produces. **Only available
  when Whisper actually ran.** When the source video has native captions,
  `_fetch_captions` returns plain text with no word timing, so
  `speech_rate_wps` is `null` in that branch.

Explicitly out of scope for v1 (dropped during brainstorming): RMS/energy,
jitter/shimmer/HNR timbre analysis. Can be added later without changing the
`voice` shape (new sibling keys).

## Pipeline integration

New function in `backend/main.py`:

```python
def _analyze_voice(audio_path: Path, segments: list[dict], duration: float) -> dict | None:
    ...
```

Pure/sync, CPU-bound — called via `asyncio.to_thread`, same pattern as the
existing OCR calls. No new job status is introduced; it runs alongside the
existing OCR fan-out in **both** existing branches:

- **Captions-found branch** (~line 829): audio was extracted but no
  Whisper `segments` exist → `speech_rate_wps: null` in both `global` and
  `hook`.
- **No-captions / Whisper branch** (~line 839): full metrics available,
  including `speech_rate_wps`.

Result lands in the same terminal `_update_job(...)` call that already sets
`transcript`/`segments`/`overlay_text`.

**Failure handling:** wrapped in try/except; on any error (corrupt audio,
librosa failure, etc.) falls back to `voice: null` rather than sinking the
job — same posture as the existing hook-microscope OCR pass.

## Dependency

Add `librosa` to `backend/requirements.txt`. Pure Python + numpy/scipy, no
native binary, no Docker image changes beyond the pip install.

## Explicitly not doing (v1)

- No new job state (`analyzing_voice`) — folds into existing `transcribing`
  step.
- No per-segment/per-word granularity — only `global` + `hook` aggregates.
- No ML-based gender classifier — heuristic F0 threshold only.
- No downstream consumer wiring (format-card, scoring, EL coaching) — this
  spec is metrics-only; consumer choice deferred until the data is seen.
