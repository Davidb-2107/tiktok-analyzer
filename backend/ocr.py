"""Server-side OCR of on-screen overlay text (TikTok captions, watermarks).

Runs RapidOCR (rapidocr-onnxruntime, PP-OCRv5 latin rec) on the local frames of
a job, then merges near-identical consecutive frames into timed spans. Exposed
on /status as two additive, absent-safe fields: overlay_text / overlay_segments.

Standalone module (main.py is not importable in tests: R2 env at top level).
Data-loss guard: ocr_frames never raises — any failure returns ('', []) so a
valid Whisper transcript is never thrown away by the surrounding gather().
"""

import difflib
import logging
import os
from pathlib import Path

logger = logging.getLogger("ocr")

_MODELS_DIR = Path(__file__).resolve().parent / "models"
REC_MODEL = _MODELS_DIR / "latin_PP-OCRv5_rec_mobile.onnx"
REC_KEYS = _MODELS_DIR / "ppocrv5_latin_dict.txt"

_engine = None
_engine_failed = False  # one-shot warning guard


def _get_engine():
    """Lazy singleton (mirror of _get_whisper). Latin rec is EXPLICIT —
    the rapidocr default is the chinese ch_PP-OCRv4 model (see ENGINE-FACTS)."""
    global _engine, _engine_failed
    if _engine is None and not _engine_failed:
        try:
            from rapidocr_onnxruntime import RapidOCR

            _engine = RapidOCR(
                use_cls=False,
                intra_op_num_threads=int(os.environ.get("OCR_THREADS", "2")),
                rec_model_path=str(REC_MODEL),
                rec_keys_path=str(REC_KEYS),
            )
        except Exception:
            _engine_failed = True
            logger.warning("OCR engine init failed — overlay fields will stay empty", exc_info=True)
    return _engine


def _read_frame(engine, path: Path) -> tuple[str, float]:
    """OCR one frame -> (joined text, mean confidence). ('' , 0.0) if no text."""
    result, _ = engine(str(path))
    if not result:
        return "", 0.0
    texts = [r[1] for r in result]
    confs = [float(r[2]) for r in result]
    return " ".join(texts), sum(confs) / len(confs)


def dedup_spans(
    frame_texts: list[tuple[str, float]], fps: float, sim: float = 0.80, bridge_gap: int = 1
) -> list[dict]:
    """Merge consecutive near-identical frame texts into timed spans.

    At 1 fps the frames of one caption are near-identical; the max-confidence
    frame wins the l<->I jitter. A dropout of up to `bridge_gap` empty frames
    inside a span is bridged.
    # ponytail: knobs sim/bridge_gap calibrated for fps=1; word-by-word
    # "karaoke" captions collapse into one span at 1 fps (known ceiling).
    """
    spans: list[dict] = []
    cur: dict | None = None
    for i, (text, conf) in enumerate(frame_texts):
        text = (text or "").strip()
        if not text:
            if cur is not None:
                cur["gap"] += 1
                if cur["gap"] > bridge_gap:
                    spans.append(cur)
                    cur = None
            continue
        if (
            cur is not None
            and difflib.SequenceMatcher(None, text.lower(), cur["text"].lower()).ratio() >= sim
        ):
            cur["end_i"] = i
            cur["gap"] = 0
            if conf > cur["conf"]:
                cur["text"], cur["conf"] = text, conf
        else:
            if cur is not None:
                spans.append(cur)
            cur = {"start_i": i, "end_i": i, "text": text, "conf": conf, "gap": 0}
    if cur is not None:
        spans.append(cur)
    return [
        {
            "start": round(s["start_i"] / fps, 2),
            "end": round((s["end_i"] + 1) / fps, 2),
            "text": s["text"],
            "confidence": round(s["conf"], 3),
        }
        for s in spans
    ]


def ocr_frames(frames_dir: Path, frame_names: list[str], fps: float) -> tuple[str, list[dict]]:
    """Same contract as _upload_frames (frames_dir + sorted frame_names).

    Returns (overlay_text, overlay_segments). NEVER raises: the whole body is
    guarded so an OCR failure can never sink the gather() that also carries
    the Whisper transcript.
    """
    try:
        if not fps or fps <= 0:
            fps = 1.0  # /analyze accepts a free float; fps=0 would divide by zero
        engine = _get_engine()
        if engine is None or not frame_names:
            return "", []
        frame_texts: list[tuple[str, float]] = []
        errors = 0
        for name in frame_names:
            try:
                frame_texts.append(_read_frame(engine, Path(frames_dir) / name))
            except Exception:
                errors += 1
                frame_texts.append(("", 0.0))
        if errors:
            logger.warning("OCR failed on %d/%d frames", errors, len(frame_names))
        segments = dedup_spans(frame_texts, fps)
        seen: set[str] = set()
        uniq = [s["text"] for s in segments if not (s["text"] in seen or seen.add(s["text"]))]
        return "\n".join(uniq), segments
    except Exception:
        logger.warning("ocr_frames failed — returning empty overlay", exc_info=True)
        return "", []


if __name__ == "__main__":
    # Self-check: dedup logic only (no model needed).
    frames = [
        ("hello world", 0.9),
        ("hello wor1d", 0.95),  # jitter — max-conf text wins
        ("", 0.0),  # dropout bridged
        ("hello world", 0.85),
        ("something else", 0.9),
        ("something else", 0.9),
    ]
    spans = dedup_spans(frames, fps=1.0)
    assert len(spans) == 2, spans
    assert spans[0]["text"] == "hello wor1d", spans
    assert spans[0]["start"] == 0.0 and spans[0]["end"] == 4.0, spans
    assert spans[1]["start"] == 4.0 and spans[1]["end"] == 6.0, spans
    assert ocr_frames(Path("."), [], 0) == ("", [])
    print("ocr.py self-check OK")
