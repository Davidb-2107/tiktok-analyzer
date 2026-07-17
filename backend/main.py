import asyncio
import ipaddress
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import boto3
import voice
import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from faster_whisper import WhisperModel
from ocr import ocr_frames
from pydantic import BaseModel

app = FastAPI(title="TikTok Analyzer")
logger = logging.getLogger("tiktok-analyzer")

# Importé avant le sys.path.insert ci-dessous : un éventuel
# Sourcing/tools/hub.py ne doit jamais shadower backend/hub.py.
import hub as niche_hub

# Local-dev-only bridge into the Wiki_Claude vault's Sourcing transcript
# registry — mounted at /sourcing/tools by docker-compose.yml (never in
# docker-compose.prod.yml, so this stays None on the public VPS deployment).
try:
    sys.path.insert(0, "/sourcing/tools")
    import transcript_registry
except ImportError:
    transcript_registry = None

MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "2"))
# Backlog cap: jobs beyond MAX_CONCURRENT_JOBS now QUEUE (status stays
# "pending" until a slot frees) instead of being rejected. 429 only fires
# when the total non-terminal backlog exceeds this.
MAX_PENDING_JOBS = int(os.environ.get("MAX_PENDING_JOBS", "20"))

# Niche Hub (dev local) : /vault est bind-monté :ro par docker-compose.yml,
# jamais en prod — sans mount, GET /hub répond 404.
VAULT_DIR = Path(os.environ.get("VAULT_DIR", "/vault"))

ACTIVE_TERMINAL = {"done", "error"}

# Serializes actual processing to MAX_CONCURRENT_JOBS. Queued _process_job
# tasks wait here with status "pending".
# ponytail: in-memory queue — pending jobs are lost on restart (swept to
# error at startup). Persist/replay the queue if that ever matters.
_job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

# --- Input guards (public endpoint) ---------------------------------------
# Only accept URLs whose host matches one of these domains (subdomains allowed,
# e.g. www.tiktok.com, vm.tiktok.com, m.youtube.com). Override via env
# ALLOWED_VIDEO_DOMAINS (comma-separated). Empty value disables the check.
_DEFAULT_ALLOWED_DOMAINS = "tiktok.com,youtube.com,youtu.be"
ALLOWED_VIDEO_DOMAINS = {
    d.strip().lower()
    for d in os.environ.get("ALLOWED_VIDEO_DOMAINS", _DEFAULT_ALLOWED_DOMAINS).split(",")
    if d.strip()
}
# Reject videos longer than this (seconds) before downloading. 0 disables the cap.
MAX_VIDEO_DURATION_SEC = int(os.environ.get("MAX_VIDEO_DURATION_SEC", "600"))
# Looser cap for transcribe=false jobs (frames+OCR only, no Whisper) — long
# YouTube masters for the Sourcing review funnel. 0 disables.
MAX_NOTRANSCRIBE_DURATION_SEC = int(os.environ.get("MAX_NOTRANSCRIBE_DURATION_SEC", "1800"))

# Optional shared secret. When set, mutating requests (POST/DELETE) must carry an
# X-API-Key header matching it. GET stays open so the SPA/polling and read-only
# sessions work without a secret. Empty value = fully open (dev behaviour).
API_KEY = os.environ.get("API_KEY", "").strip()
_PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


# Registered BEFORE CORS so the CORS middleware stays outermost and 401 responses
# still carry CORS headers (browsers can then read the error body).
@app.middleware("http")
async def _api_key_guard(request, call_next):
    if API_KEY and request.method in _PROTECTED_METHODS and request.headers.get("X-API-Key") != API_KEY:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing X-API-Key."})
    return await call_next(request)


_allowed_origin = os.environ.get("ALLOWED_ORIGIN", "*")
app.add_middleware(CORSMiddleware, allow_origins=[_allowed_origin], allow_methods=["*"], allow_headers=["*"])

TEMP_DIR = Path("/app/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _sweep_orphans_sync() -> None:
    """Jobs interrupted by a restart (in-flight or queued) would otherwise sit
    non-terminal forever — the frontend would poll them for eternity and they
    would count against the MAX_PENDING_JOBS backlog cap. Sweeping to error is
    a terminal transition, so the webhook contract applies here too."""
    for job_dir in TEMP_DIR.iterdir():
        f = job_dir / "job.json"
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text())
            if data.get("status") not in ACTIVE_TERMINAL:
                data.update(status="error", error="Interrupted by server restart.")
                f.write_text(json.dumps(data))
                _send_webhook(job_dir.name)  # never raises
        except Exception:
            logger.exception("orphan sweep failed for %s", job_dir.name)


@app.on_event("startup")
async def _sweep_orphaned_jobs() -> None:
    # Fire-and-forget off the event loop: the sweep reads every job dir and
    # webhook deliveries carry 10s timeouts — serving /health must not wait.
    t = asyncio.get_running_loop().create_task(asyncio.to_thread(_sweep_orphans_sync))
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)


R2_BUCKET = os.environ["R2_BUCKET"]
R2_ENDPOINT = os.environ["R2_ENDPOINT"]
PRESIGN_TTL = 3600

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
)

WHISPER_MODEL_NAME = os.environ.get("WHISPER_MODEL", "medium")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
# 5 (faster-whisper default) over the previous 10: ~30-40% faster on CPU for a
# marginal WER difference — transcripts feed analysis pipelines, not published
# subtitles. Env-overridable to A/B on hard audio (loud music, fast speech).
WHISPER_BEAM_SIZE = int(os.environ.get("WHISPER_BEAM_SIZE", "5"))

# Hook microscope: a denser OCR pass over the opening seconds, where a video
# wins or loses attention. Overlay captions there often flash <1s and are missed
# by the 1fps main pass; HOOK_FPS samples them finer. Purely additive — never
# touches the main frame set or the job fps. Both env-overridable.
HOOK_WINDOW_S = float(os.environ.get("HOOK_WINDOW_S", "5"))
HOOK_FPS = float(os.environ.get("HOOK_FPS", "2"))

# Focused-window pass (start_s/end_s on /analyze): denser than the main pass,
# same rationale as HOOK_FPS above but independently tunable since a caller-
# requested window and the opening-seconds hook can diverge later.
WINDOW_FPS = float(os.environ.get("WINDOW_FPS", "2"))

_whisper_model: WhisperModel | None = None


def _get_whisper() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(
            WHISPER_MODEL_NAME, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE
        )
    return _whisper_model


def _transcribe(audio_path: Path) -> tuple[str, list[dict]]:
    """Return (full_text, segments). Each segment dict has start/end/text and
    an optional `words` list of {start, end, word}. word_timestamps=True is
    required by the SRT endpoint — keep on unless you also drop /captions.srt."""
    segments_iter, _info = _get_whisper().transcribe(
        str(audio_path),
        beam_size=WHISPER_BEAM_SIZE,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        word_timestamps=True,
    )
    segments: list[dict] = []
    text_parts: list[str] = []
    for seg in segments_iter:
        seg_text = (seg.text or "").strip()
        text_parts.append(seg_text)
        seg_dict: dict = {
            "start": float(seg.start) if seg.start is not None else 0.0,
            "end": float(seg.end) if seg.end is not None else 0.0,
            "text": seg_text,
        }
        words = getattr(seg, "words", None)
        if words:
            seg_dict["words"] = [
                {
                    "start": float(w.start) if w.start is not None else 0.0,
                    "end": float(w.end) if w.end is not None else 0.0,
                    "word": (w.word or "").strip(),
                }
                for w in words
            ]
        segments.append(seg_dict)
    return " ".join(t for t in text_parts if t).strip(), segments


# In-container path mounted from host (see docker-compose). When set, every job
# transition to "done" with a transcript also drops a raw `.txt` into this dir
# so external pipelines (e.g. Psycho ingest skill) pick it up automatically.
SCRIPT_INBOX_DIR = os.environ.get("SCRIPT_INBOX_DIR")

# Per-project inbox overrides. Looked up as INBOX_<PROJECT_UPPER>. When a job
# carries a project tag, _write_script consults the matching env var to pick
# the host folder; falls back to SCRIPT_INBOX_DIR. Project 'archive' skips the
# inbox drop entirely (still writes temp/{id}/script.txt).
KNOWN_PROJECTS = {"psycho", "archive"}
ARCHIVE_PROJECT = "archive"


def _inbox_dir_for_project(project: str | None) -> str | None:
    if project:
        override = os.environ.get(f"INBOX_{project.upper()}")
        if override:
            return override
    return SCRIPT_INBOX_DIR


_TIKTOK_URL_RE = re.compile(r"tiktok\.com/@([^/?]+)/video/(\d+)")
_YOUTUBE_URL_RE = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/))([\w-]+)")
# Instagram URLs: optional username segment before reel/p/tv
# Examples: instagram.com/reel/CxYz/, instagram.com/joe.doe/reel/CxYz/
_INSTAGRAM_URL_RE = re.compile(r"instagram\.com/(?:([\w.]+)/)?(?:reel|reels|p|tv)/([\w-]+)")


def _parse_source(url: str) -> dict:
    m = _TIKTOK_URL_RE.search(url or "")
    if m:
        return {"platform": "tiktok", "author": f"@{m.group(1)}", "video_id": m.group(2)}
    m = _INSTAGRAM_URL_RE.search(url or "")
    if m:
        author = f"@{m.group(1)}" if m.group(1) else "unknown"
        return {"platform": "instagram", "author": author, "video_id": m.group(2)}
    m = _YOUTUBE_URL_RE.search(url or "")
    if m:
        return {"platform": "youtube", "author": "unknown", "video_id": m.group(1)}
    return {"platform": "unknown", "author": "unknown", "video_id": "unknown"}


def _resolve_author(job: dict) -> str:
    """Persisted yt-dlp uploader wins (always populated when known by source).
    Fall back to URL-regex-parsed author. 'unknown' as last resort."""
    persisted = (job.get("author") or "").strip()
    if persisted:
        return persisted if persisted.startswith("@") else f"@{persisted}"
    return _parse_source(job.get("url", ""))["author"]


def _safe_slug(s: str) -> str:
    return re.sub(r"[^\w.-]", "_", s).strip("_") or "unknown"


def _build_script_text(job: dict) -> str:
    author = _resolve_author(job)
    transcribed = datetime.now(UTC).astimezone().isoformat(timespec="seconds")
    model_info = f"faster-whisper-{WHISPER_MODEL_NAME} {WHISPER_COMPUTE_TYPE} {WHISPER_DEVICE} beam={WHISPER_BEAM_SIZE}"
    headers = [
        f"# SOURCE: {job.get('url', '')}",
        f"# AUTHOR: {author}",
        f"# DURATION_S: {job.get('duration') if job.get('duration') is not None else '?'}",
    ]
    # Engagement metrics from yt-dlp at download time. Lines omitted when
    # the platform/account did not expose the metric (Insta private, etc.).
    metric_labels = [("views", "VIEWS"), ("likes", "LIKES"), ("comments", "COMMENTS"), ("shares", "SHARES")]
    metrics = job.get("metrics") or {}
    for key, label in metric_labels:
        v = metrics.get(key)
        if v is not None:
            headers.append(f"# {label}: {v}")
    # Hashtags + caption description (both optional — omitted when missing
    # / empty). Inserted BEFORE the TRANSCRIBED line so the temporal
    # markers (TRANSCRIBED / MODEL) remain at the bottom of the header.
    tags = metrics.get("tags") or []
    if tags:
        headers.append(f"# TAGS: {', '.join(str(t) for t in tags)}")
    # User-managed tags (set via PATCH /jobs/{id}/tags). Placed immediately
    # after platform # TAGS so both tag-spaces sit together; omitted if empty.
    user_tags = job.get("user_tags") or []
    if user_tags:
        headers.append(f"# USER_TAGS: {', '.join(str(t) for t in user_tags)}")
    description = metrics.get("description") or ""
    if description:
        # Collapse any newlines / runs of whitespace into single spaces so
        # the CAPTION line stays single-line as required.
        single_line = re.sub(r"\s+", " ", description).strip()
        if single_line:
            headers.append(f"# CAPTION: {single_line}")
    headers += [f"# TRANSCRIBED: {transcribed}", f"# MODEL: {model_info}"]
    return "\n".join(headers) + "\n\n" + (job.get("transcript") or "") + "\n"


def _job_day(job: dict) -> str:
    """Filename date prefix — derived from the job's `created_at` so a single
    job always produces the same inbox filename across re-runs (backfill,
    refresh, retag, etc.). Falls back to today if created_at is missing or
    malformed. ISO timestamps always start with `YYYY-MM-DD` so slicing the
    first 10 chars is safe and avoids parsing overhead."""
    s = job.get("created_at") or ""
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _write_script(job_id: str) -> None:
    """On job done with transcript: write to temp/{job_id}/script.txt and
    mirror into the project-specific inbox (or SCRIPT_INBOX_DIR fallback) if
    configured. Project 'archive' skips the inbox drop. Silently no-op if no
    transcript. Filename uses job.created_at so re-runs are idempotent."""
    job = _load_job(job_id) or {}
    if not job.get("transcript"):
        return
    body = _build_script_text(job)
    (TEMP_DIR / job_id / "script.txt").write_text(body, encoding="utf-8")
    project = job.get("project")
    if project == ARCHIVE_PROJECT:
        return
    inbox_dir = _inbox_dir_for_project(project)
    if inbox_dir:
        author = _resolve_author(job)
        video_id = _parse_source(job.get("url", ""))["video_id"]
        day = _job_day(job)
        filename = f"{day}_{_safe_slug(author)}_{_safe_slug(video_id)}.txt"
        inbox = Path(inbox_dir)
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / filename).write_text(body, encoding="utf-8")


def _write_audio(job_id: str) -> None:
    """Mirror the extracted audio.mp3 into the project inbox using the same
    {date}_{author}_{video_id}.mp3 naming as the script.txt drop, so .txt
    and .mp3 form a deterministic pair. Skips when project='archive' (matches
    _write_script) and when audio.mp3 is missing."""
    job = _load_job(job_id) or {}
    src = _audio_path(job_id)
    if not src.exists():
        return
    project = job.get("project")
    if project == ARCHIVE_PROJECT:
        return
    inbox_dir = _inbox_dir_for_project(project)
    if not inbox_dir:
        return
    author = _resolve_author(job)
    video_id = _parse_source(job.get("url", ""))["video_id"]
    day = _job_day(job)
    filename = f"{day}_{_safe_slug(author)}_{_safe_slug(video_id)}.mp3"
    inbox = Path(inbox_dir)
    inbox.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, inbox / filename)


JobStatus = Literal["pending", "downloading", "extracting", "frames_ready", "transcribing", "done", "error"]


class AnalyzeRequest(BaseModel):
    url: str
    fps: float | None = None
    project: str | None = None
    start_s: float | None = None
    end_s: float | None = None
    # Optional: POSTed the final job payload when the job reaches done/error.
    webhook_url: str | None = None
    # False = frames + OCR only (no captions fetch, no Whisper, no audio) —
    # for footage QC on long videos where a transcript is useless.
    transcribe: bool = True


class BatchAnalyzeRequest(BaseModel):
    urls: list[str]
    fps: float | None = None
    project: str | None = None
    webhook_url: str | None = None
    transcribe: bool = True


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


class UserTagsRequest(BaseModel):
    tags: list[str] = []


class SaveTranscriptRequest(BaseModel):
    niche: str
    channel: str | None = None
    title: str | None = None
    views: int | None = None


def _job_file(job_id: str) -> Path:
    return TEMP_DIR / job_id / "job.json"


def _frames_dir(job_id: str) -> Path:
    return TEMP_DIR / job_id / "frames"


def _hook_frames_dir(job_id: str) -> Path:
    return TEMP_DIR / job_id / "frames_hook"


def _audio_path(job_id: str) -> Path:
    return TEMP_DIR / job_id / "audio.mp3"


def _load_job(job_id: str) -> dict | None:
    f = _job_file(job_id)
    if not f.exists():
        return None
    return json.loads(f.read_text())


def _save_job(job_id: str, data: dict) -> None:
    _job_file(job_id).write_text(json.dumps(data))


def _update_job(job_id: str, **kwargs) -> None:
    data = _load_job(job_id) or {}
    data.update(kwargs)
    _save_job(job_id, data)


def _presign_key(key: str) -> str:
    return s3.generate_presigned_url(
        "get_object", Params={"Bucket": R2_BUCKET, "Key": key}, ExpiresIn=PRESIGN_TTL
    )


def _resolve_frames(job_id: str, job: dict) -> dict:
    """Enrich job with frame data ready for the frontend.

    frames_ready / transcribing: frames are local filenames (upload runs in
    parallel with Whisper during transcribing). Return as-is, frontend
    constructs URLs using its own API base URL.
    done: frames are R2 keys — presign them.
    """
    status = job.get("status")
    frames = job.get("frames", [])
    if not frames:
        return job

    if status == "done":
        return {**job, "frames": [_presign_key(k) for k in frames]}

    # frames_ready, transcribing: local filenames
    return job


def _download_video(url: str, output_path: Path) -> tuple[Path, float, str | None, dict]:
    ydl_opts = {
        "format": "best[height<=1080]/best[ext=mp4]/best",
        "outtmpl": str(output_path / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_path = output_path / f"{info['id']}.{info['ext']}"
        duration = float(info.get("duration") or 0)
        # Prefer the first non-numeric candidate (TikTok returns numeric
        # uploader_id; Instagram returns the handle as uploader_id).
        uploader = next(
            (
                v
                for v in (info.get("uploader_id"), info.get("uploader"), info.get("channel"))
                if v and not str(v).isdigit()
            ),
            None,
        )
        # Hashtags (list[str]) and full caption description from yt-dlp.
        # Kept inside the same `metrics` dict so existing persistence
        # (`_update_job(..., metrics=metrics)`) carries them without
        # signature churn or extra storage keys.
        raw_tags = info.get("tags") or []
        tags = [str(t).lstrip("#").strip() for t in raw_tags if str(t).strip()]
        description = info.get("description") or ""
        metrics = {
            "views": info.get("view_count"),
            "likes": info.get("like_count"),
            "comments": info.get("comment_count"),
            "shares": info.get("repost_count"),
            "tags": tags,
            "description": description,
        }
        return video_path, duration, uploader, metrics


def _extract_audio(video_path: Path, audio_path: Path) -> None:
    cmd = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-q:a",
        "4",
        str(audio_path),
        "-y",
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def _extract_frames(
    video_path: Path, out_dir: Path, fps: float, limit_s: float | None = None, start_s: float | None = None
) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = str(out_dir / "frame_%03d.jpg")
    base_vf = f"setpts=PTS-STARTPTS,fps={fps},format=yuvj420p"
    # Output-side trim (right before the pattern) so BOTH the plain decode and
    # the HEVC retry inherit the cap. None = whole video (the main pass); the
    # hook pass passes limit_s to grab only the opening window.
    limit = ["-t", str(limit_s)] if limit_s else []
    # Input-side seek (-ss before -i): fast, keyframe-aligned. Good enough for
    # vision-reasoning frame grabs, not for frame-accurate editing. Lives
    # inside run() below (not appended per call-site) so both the plain decode
    # AND the HEVC retry inherit it automatically.
    seek = ["-ss", str(start_s)] if start_s else []

    def run(extra: list[str]) -> subprocess.CompletedProcess:
        cmd = [
            "ffmpeg",
            *extra,
            *seek,
            "-i",
            str(video_path),
            "-vf",
            base_vf,
            "-q:v",
            "2",
            *limit,
            output_pattern,
            "-y",
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    # First try: plain decode. Some HEVC TikTok sources tag VUI colour as
    # "reserved", which the filter-graph autoscaler rejects with
    # "Invalid color space". Retry with a hevc_metadata bitstream filter that
    # rewrites VUI to bt709 before decoding.
    result = run([])
    if result.returncode != 0 and "Invalid color space" in result.stderr:
        result = run(
            ["-bsf:v", "hevc_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1"]
        )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    return [p.name for p in sorted(out_dir.glob("frame_*.jpg"))]


def _ahash(path: Path, size: int = 8) -> int:
    """8x8 grayscale average-hash -> 64-bit int. PIL only (transitive dep of
    rapidocr-onnxruntime, already installed)."""
    from PIL import Image

    img = Image.open(path).convert("L").resize((size, size), Image.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p >= avg else "0" for p in pixels)
    return int(bits, 2)


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _dedup_frames(out_dir: Path, frame_names: list[str], max_hamming: int = 4) -> list[str]:
    """Drop consecutive near-duplicate frames (aHash Hamming distance <=
    max_hamming) before OCR/upload — a held title card or static slide
    shouldn't bill as N separate frames. Keeps order, always keeps the first
    frame. Dropped files are unlinked from disk. Never raises — a hashing
    failure just keeps every frame (same defensive shape as ocr_frames)."""
    try:
        kept: list[str] = []
        prev_hash = None
        for name in frame_names:
            h = _ahash(out_dir / name)
            if prev_hash is not None and _hamming(h, prev_hash) <= max_hamming:
                (out_dir / name).unlink(missing_ok=True)
                continue
            kept.append(name)
            prev_hash = h
        dropped = len(frame_names) - len(kept)
        if dropped:
            logger.info("dedup: dropped %d/%d near-duplicate frames", dropped, len(frame_names))
        return kept
    except Exception:
        logger.exception("dedup: hashing failed, keeping all frames")
        return frame_names


def _fetch_captions(url: str, output_path: Path) -> str | None:
    ydl_opts = {
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "en-GB"],
        "subtitlesformat": "vtt",
        "outtmpl": str(output_path / "captions"),
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    vtt_files = list(output_path.glob("captions*.vtt"))
    if not vtt_files:
        return None

    raw = vtt_files[0].read_text(encoding="utf-8")
    vtt_files[0].unlink()
    return _parse_vtt(raw)


def _parse_vtt(vtt: str) -> str:
    lines = vtt.splitlines()
    text_lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("WEBVTT") or "-->" in line or re.match(r"^\d+$", line):
            continue
        clean = re.sub(r"<[^>]+>", "", line)
        if clean and (not text_lines or clean != text_lines[-1]):
            text_lines.append(clean)
    return " ".join(text_lines)


def _upload_frames(job_id: str, frame_names: list[str]) -> list[str]:
    """Upload local frames to R2, return R2 keys."""
    keys = []
    src_dir = _frames_dir(job_id)
    for name in frame_names:
        key = f"{job_id}/{name}"
        s3.upload_file(str(src_dir / name), R2_BUCKET, key, ExtraArgs={"ContentType": "image/jpeg"})
        keys.append(key)
    return keys


def _ocr_main_and_hook(
    job_id: str, frame_names: list[str], fps: float, hook_names: list[str]
) -> tuple[tuple[str, list[dict]], tuple[str, list[dict]]]:
    """Main + hook OCR back-to-back in ONE thread, so the surrounding gather
    keeps its concurrent-task count (upload + Whisper + this) unchanged — the
    ~HOOK_FPS*HOOK_WINDOW_S extra hook frames add a few serial seconds that stay
    hidden under the far slower Whisper pass. ocr_frames never raises, so a hook
    failure can't sink the main overlay or the transcript."""
    main = ocr_frames(_frames_dir(job_id), frame_names, fps)
    hook = ocr_frames(_hook_frames_dir(job_id), hook_names, HOOK_FPS)
    return main, hook


async def _process_job(
    job_id: str,
    url: str,
    fps: float,
    start_s: float | None = None,
    end_s: float | None = None,
    transcribe: bool = True,
) -> None:
    """Queue gate + terminal webhook around the actual pipeline. Status stays
    "pending" while waiting for a concurrency slot — that IS the queue."""
    async with _job_semaphore:
        await _run_job(job_id, url, fps, start_s, end_s, transcribe)
    await asyncio.to_thread(_send_webhook, job_id)


async def _run_job(
    job_id: str,
    url: str,
    fps: float,
    start_s: float | None = None,
    end_s: float | None = None,
    transcribe: bool = True,
) -> None:
    job_dir = TEMP_DIR / job_id
    window = start_s is not None or end_s is not None

    try:
        _update_job(job_id, status="downloading")
        video_path, duration, uploader, metrics = await asyncio.to_thread(_download_video, url, job_dir)

        audio_path = _audio_path(job_id)
        if transcribe:
            await asyncio.to_thread(_extract_audio, video_path, audio_path)

        _update_job(job_id, status="extracting")
        if window:
            # Focused window: caller asked for a specific slice, so it IS the
            # dense pass — skip the full-video pass and the hook microscope
            # entirely (a redundant dense pass over part of the window would
            # just waste OCR time).
            w_start = start_s or 0.0
            w_end = end_s if end_s is not None else duration
            # Cap the window's frame budget: WINDOW_FPS=2 is meant for short
            # hook-style slices; a long window (now reachable via the 1800s
            # transcribe=false cap) at flat 2fps would extract thousands of
            # frames. 240 ≈ 2 minutes of dense sampling.
            span = max(w_end - w_start, 1.0)
            fps = min(WINDOW_FPS, 240 / span)
            frame_names = await asyncio.to_thread(
                _extract_frames, video_path, _frames_dir(job_id), fps, span, w_start
            )
            frame_names = await asyncio.to_thread(_dedup_frames, _frames_dir(job_id), frame_names)
            hook_frame_names: list[str] = []
        else:
            frame_names = await asyncio.to_thread(_extract_frames, video_path, _frames_dir(job_id), fps)
            frame_names = await asyncio.to_thread(_dedup_frames, _frames_dir(job_id), frame_names)
            # Hook microscope: denser 2fps pass over the first HOOK_WINDOW_S seconds.
            # Best-effort — an ffmpeg failure here must NEVER sink the job (the main
            # frames + transcript are what matter), so we swallow it to an empty set.
            try:
                hook_frame_names = await asyncio.to_thread(
                    _extract_frames, video_path, _hook_frames_dir(job_id), HOOK_FPS, HOOK_WINDOW_S
                )
            except Exception:
                hook_frame_names = []
        video_path.unlink(missing_ok=True)

        # Frames are local — frontend can display them immediately
        _update_job(
            job_id,
            status="frames_ready",
            frames=frame_names,
            duration=duration,
            author=uploader,
            metrics=metrics,
            fps=fps,
            start_s=start_s,
            end_s=end_s,
        )

        # Captions check first (cheap — yt-dlp metadata). Decides whether
        # to run upload alone, or upload + Whisper truly in parallel.
        # transcribe=False skips both captions and Whisper: the first branch
        # below (upload + OCR only) runs with transcript=None.
        transcript = None
        if transcribe:
            transcript = await asyncio.to_thread(_fetch_captions, url, job_dir)

        segments: list[dict] = []
        voice_metrics: dict | None = None
        if transcript or not transcribe:
            gather_tasks = [
                asyncio.to_thread(_upload_frames, job_id, frame_names),
                asyncio.to_thread(_ocr_main_and_hook, job_id, frame_names, fps, hook_frame_names),
            ]
            if transcribe:
                gather_tasks.append(
                    asyncio.to_thread(voice.analyze_voice, audio_path, segments, duration, HOOK_WINDOW_S)
                )
            gather_results = await asyncio.gather(*gather_tasks)
            (r2_keys, ((overlay_text, overlay_segments), (hook_overlay_text, hook_overlay_segments))) = (
                gather_results[0],
                gather_results[1],
            )
            voice_metrics = gather_results[2] if transcribe else None
        else:
            # No captions: frames still local. Mark transcribing so the UI shows
            # progress, then fan out upload + Whisper concurrently.
            _update_job(job_id, status="transcribing", frames=frame_names)
            r2_keys, transcribe_result, ocr_result = await asyncio.gather(
                asyncio.to_thread(_upload_frames, job_id, frame_names),
                asyncio.to_thread(_transcribe, audio_path),
                asyncio.to_thread(_ocr_main_and_hook, job_id, frame_names, fps, hook_frame_names),
            )
            transcript, segments = transcribe_result
            ((overlay_text, overlay_segments), (hook_overlay_text, hook_overlay_segments)) = ocr_result
            voice_metrics = await asyncio.to_thread(
                voice.analyze_voice, audio_path, segments, duration, HOOK_WINDOW_S
            )

        shutil.rmtree(_frames_dir(job_id), ignore_errors=True)
        shutil.rmtree(_hook_frames_dir(job_id), ignore_errors=True)
        # Keep audio_path on disk (temp/{job_id}/audio.mp3) — needed by the
        # /audio.mp3 endpoint and the inbox mirror for downstream voice
        # analysis (parselmouth/Praat, ElevenLabs cloning, etc.).
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
        _write_script(job_id)
        _write_audio(job_id)

    except Exception as exc:
        _update_job(job_id, status="error", error=str(exc))


def _count_active_jobs() -> int:
    count = 0
    for job_dir in TEMP_DIR.iterdir():
        f = job_dir / "job.json"
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text())
            if data.get("status") not in ACTIVE_TERMINAL:
                count += 1
        except Exception:
            pass
    return count


def _validate_url_domain(url: str) -> None:
    """Reject malformed URLs and hosts outside ALLOWED_VIDEO_DOMAINS.

    Subdomains of an allowed domain pass (host == d or host endswith '.'+d).
    Raises HTTPException(422) on rejection. No-op when the allowlist is empty.
    """
    try:
        parsed = urllib.parse.urlparse(url.strip())
    except Exception:
        raise HTTPException(status_code=422, detail="Malformed URL.")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=422, detail="URL must be an http(s) link.")
    if not ALLOWED_VIDEO_DOMAINS:
        return
    host = parsed.hostname.lower()
    if not any(host == d or host.endswith("." + d) for d in ALLOWED_VIDEO_DOMAINS):
        raise HTTPException(
            status_code=422, detail=f"Domain '{host}' not allowed. Allowed: {sorted(ALLOWED_VIDEO_DOMAINS)}."
        )


def _webhook_host_is_public(host: str) -> bool:
    """True iff every address the host resolves to is a global (public) IP.
    Resolution failure = not public (fail closed). Called both at request
    time (fast 422) and again right before delivery, which shrinks the
    DNS-rebinding window to the resolve->connect gap of a single send.
    # ponytail: full rebind-proofing would pin the resolved IP into the
    # connection; revisit if this service ever handles hostile traffic at scale.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    try:
        return all(ipaddress.ip_address(i[4][0]).is_global for i in infos)
    except ValueError:
        return False


def _validate_webhook_url(url: str) -> None:
    """Reject non-http(s) and internal webhook targets (SSRF guard). The API
    is public, so hostnames are RESOLVED and every resulting IP must be
    global — literal-IP checks alone are trivially bypassed via DNS."""
    try:
        parsed = urllib.parse.urlparse(url.strip())
    except Exception:
        raise HTTPException(status_code=422, detail="Malformed webhook_url.")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=422, detail="webhook_url must be an http(s) link.")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local"):
        raise HTTPException(status_code=422, detail="webhook_url must not target internal hosts.")
    if not _webhook_host_is_public(host):
        raise HTTPException(status_code=422, detail="webhook_url must resolve to public IPs only.")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # A 302 to an internal address would bypass the resolve-time SSRF check;
    # webhooks have no legitimate need to redirect.
    def redirect_request(self, *args, **kwargs):
        return None


_webhook_opener = urllib.request.build_opener(_NoRedirect)


def _send_webhook(job_id: str) -> None:
    """POST the final job payload to the job's webhook_url, if any. Best-effort:
    the job is already terminal, so any failure only logs a warning."""
    try:
        job = _load_job(job_id) or {}
        url = job.get("webhook_url")
        if not url:
            return
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        if not host or not _webhook_host_is_public(host):
            logger.warning("webhook host no longer public for job %s", job_id)
            return
        payload = {"job_id": job_id, **_resolve_frames(job_id, job)}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _webhook_opener.open(req, timeout=10):
            pass
    except Exception:
        logger.warning("webhook delivery failed for job %s", job_id, exc_info=True)


def _probe_duration(url: str) -> float:
    """Fetch video duration (seconds) via yt-dlp metadata WITHOUT downloading."""
    ydl_opts = {"skip_download": True, "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return float(info.get("duration") or 0)


def _adaptive_fps(duration: float) -> float:
    """fps = target_frame_count / duration, clamped. Small lookup table (same
    'reasonable constant, not a formula' precedent as HOOK_FPS) rather than a
    curve fit — used only when the caller omits `fps` entirely."""
    if duration <= 0:
        return 1.0  # unknown duration: fall back to the old flat default
    if duration <= 30:
        target = 30
    elif duration <= 60:
        target = 40
    elif duration <= 180:
        target = 60
    elif duration <= 600:
        target = 80
    else:
        target = 100
    # Floor 0.05 (1 frame / 20s), not 0.2: a 0.2 floor inflates long videos
    # way past their target budget (25min -> 300 frames instead of ~100).
    return min(max(target / duration, 0.05), 5.0)


def _normalize_project(project: str | None) -> str | None:
    if project is not None:
        project = project.strip().lower() or None
    if project is not None and project not in KNOWN_PROJECTS:
        raise HTTPException(
            status_code=422, detail=f"Unknown project '{project}'. Allowed: {sorted(KNOWN_PROJECTS)} or null."
        )
    return project


async def _probe_and_pick_fps(url: str, fps_req: float | None, transcribe: bool = True) -> float:
    """Duration-cap check (probed before download) + adaptive fps when the
    caller omitted fps. Raises HTTPException on probe failure or over-cap.
    transcribe=False jobs get the looser MAX_NOTRANSCRIBE_DURATION_SEC cap."""
    cap = MAX_VIDEO_DURATION_SEC if transcribe else MAX_NOTRANSCRIBE_DURATION_SEC
    probed: float | None = None
    if cap > 0 or fps_req is None:
        try:
            probed = await asyncio.to_thread(_probe_duration, url)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Could not read video metadata: {exc}")
        if cap > 0 and probed > cap:
            raise HTTPException(status_code=422, detail=(f"Video too long ({int(probed)}s > {cap}s cap)."))
    return fps_req if fps_req is not None else _adaptive_fps(probed or 0.0)


# Fire-and-forget job tasks. NOT BackgroundTasks: starlette runs a request's
# background tasks sequentially, which would serialize a whole batch onto one
# concurrency slot. Strong refs kept until done (create_task alone can be GC'd).
_bg_tasks: set[asyncio.Task] = set()


def _spawn_job(
    job_id: str,
    url: str,
    fps: float,
    start_s: float | None = None,
    end_s: float | None = None,
    transcribe: bool = True,
) -> None:
    t = asyncio.get_running_loop().create_task(_process_job(job_id, url, fps, start_s, end_s, transcribe))
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)


def _register_job(url: str, project: str | None, webhook_url: str | None, transcribe: bool = True) -> str:
    # Authoritative backlog check. The endpoint-level gate is only a fast-fail
    # snapshot taken BEFORE the multi-second yt-dlp probes — concurrent
    # requests all pass it (TOCTOU). This function is synchronous (no await
    # between count and write), so on a single event loop it cannot race.
    if _count_active_jobs() >= MAX_PENDING_JOBS:
        raise HTTPException(status_code=429, detail=f"Job backlog full (max {MAX_PENDING_JOBS} pending).")
    job_id = str(uuid.uuid4())
    (TEMP_DIR / job_id).mkdir(parents=True, exist_ok=True)
    _save_job(
        job_id,
        {
            "status": "pending",
            "frames": [],
            "error": None,
            "url": url,
            "transcript": None,
            "duration": None,
            "project": project,
            "webhook_url": webhook_url,
            "transcribe": transcribe,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    return job_id


@app.post("/analyze", response_model=JobResponse)
async def analyze(request: AnalyzeRequest):
    if _count_active_jobs() >= MAX_PENDING_JOBS:
        raise HTTPException(
            status_code=429,
            detail=f"Job backlog full (max {MAX_PENDING_JOBS} pending). Wait for current jobs to finish.",
        )
    _validate_url_domain(request.url)
    if request.webhook_url:
        _validate_webhook_url(request.webhook_url)
    if request.start_s is not None and request.start_s < 0:
        raise HTTPException(status_code=422, detail="start_s must be >= 0.")
    if request.end_s is not None and request.end_s <= (request.start_s or 0):
        raise HTTPException(status_code=422, detail="end_s must be greater than start_s.")
    project = _normalize_project(request.project)
    fps = await _probe_and_pick_fps(request.url, request.fps, request.transcribe)
    job_id = _register_job(request.url, project, request.webhook_url, request.transcribe)
    _spawn_job(job_id, request.url, fps, request.start_s, request.end_s, request.transcribe)
    return JobResponse(job_id=job_id, status="pending", url=request.url, project=project)


@app.post("/analyze/batch")
async def analyze_batch(request: BatchAnalyzeRequest):
    """Create one job per URL. Per-URL validation/probe failures land in
    `rejected` (with the reason) instead of failing the whole batch."""
    urls = list(dict.fromkeys(u.strip() for u in request.urls if u.strip()))
    if not urls:
        raise HTTPException(status_code=422, detail="urls must contain at least one URL.")
    if len(urls) > 20:
        raise HTTPException(status_code=422, detail="Max 20 URLs per batch.")
    project = _normalize_project(request.project)
    if request.webhook_url:
        _validate_webhook_url(request.webhook_url)
    if _count_active_jobs() + len(urls) > MAX_PENDING_JOBS:
        raise HTTPException(
            status_code=429, detail=f"Batch would exceed the job backlog cap ({MAX_PENDING_JOBS} pending)."
        )

    async def prepare(u: str) -> dict:
        try:
            _validate_url_domain(u)
            return {"url": u, "fps": await _probe_and_pick_fps(u, request.fps, request.transcribe)}
        except HTTPException as exc:
            return {"url": u, "reason": exc.detail}

    prepared = await asyncio.gather(*(prepare(u) for u in urls))
    jobs, rejected = [], []
    for p in prepared:
        if "reason" in p:
            rejected.append(p)
            continue
        try:
            job_id = _register_job(p["url"], project, request.webhook_url, request.transcribe)
        except HTTPException as exc:
            # Backlog filled mid-batch (concurrent submits): remaining URLs
            # land in `rejected` instead of failing the whole request.
            rejected.append({"url": p["url"], "reason": exc.detail})
            continue
        _spawn_job(job_id, p["url"], p["fps"], transcribe=request.transcribe)
        jobs.append({"url": p["url"], "job_id": job_id})
    return {"jobs": jobs, "rejected": rejected}


@app.get("/channel/top")
async def channel_top(url: str, n: int = 10):
    """Enumerate a channel/profile page (yt-dlp flat playlist) and return its
    top-N videos by view count — the entry point of the format-study chain
    (channel URL -> top videos -> /analyze/batch -> extract-format)."""
    _validate_url_domain(url)
    n = max(1, min(n, 20))

    def enumerate_channel() -> list[dict]:
        opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "playlistend": 200,  # enumeration cap; enough to find a channel's tops
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        vids = []
        for e in info.get("entries") or []:
            # Entries without a usable URL would poison the documented
            # pipe into /analyze/batch (urls: list[str] rejects null).
            if not e or not (e.get("url") or e.get("webpage_url")):
                continue
            vids.append(
                {
                    "url": e.get("url") or e.get("webpage_url"),
                    "title": e.get("title"),
                    "views": e.get("view_count") or e.get("play_count") or 0,
                    "duration": e.get("duration"),
                }
            )
        vids.sort(key=lambda v: v["views"] or 0, reverse=True)
        return vids

    try:
        vids = await asyncio.to_thread(enumerate_channel)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Channel enumeration failed: {exc}")
    if not vids:
        raise HTTPException(status_code=404, detail="No videos found (not a channel/profile URL?)")
    return {"channel": url, "enumerated": len(vids), "top": vids[:n]}


@app.get("/frames/{job_id}/local/{frame_name}")
async def get_local_frame(job_id: str, frame_name: str):
    frame_path = _frames_dir(job_id) / frame_name
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="Frame not found")
    return FileResponse(frame_path, media_type="image/jpeg")


def _format_srt_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS,mmm per SRT spec."""
    if seconds is None or seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3600 * 1000)
    minutes, rem = divmod(rem, 60 * 1000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _build_srt(segments: list[dict]) -> str:
    cues: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        start = _format_srt_timestamp(seg.get("start", 0.0) or 0.0)
        end = _format_srt_timestamp(seg.get("end", 0.0) or 0.0)
        text = (seg.get("text") or "").strip()
        cues.append(f"{idx}\n{start} --> {end}\n{text}\n")
    return "\n".join(cues)


@app.get("/jobs/{job_id}/captions.srt")
async def get_captions_srt(job_id: str):
    from fastapi.responses import Response

    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    segments = job.get("segments") or []
    if not segments:
        raise HTTPException(status_code=404, detail="No segments for this job")
    body = _build_srt(segments)
    author = _resolve_author(job)
    video_id = _parse_source(job.get("url", ""))["video_id"]
    download_name = f"{_safe_slug(author)}_{_safe_slug(video_id)}.srt"
    return Response(
        content=body,
        media_type="application/x-subrip",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@app.get("/jobs/{job_id}/script.txt")
async def get_script(job_id: str):
    script_path = TEMP_DIR / job_id / "script.txt"
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")
    job = _load_job(job_id) or {}
    author = _resolve_author(job)
    video_id = _parse_source(job.get("url", ""))["video_id"]
    download_name = f"{_safe_slug(author)}_{_safe_slug(video_id)}.txt"
    return FileResponse(script_path, media_type="text/plain; charset=utf-8", filename=download_name)


@app.get("/jobs/{job_id}/audio.mp3")
async def get_audio(job_id: str):
    audio_path = _audio_path(job_id)
    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Audio not found (transcribe=false jobs never extract audio; "
                "older jobs ran before audio retention was enabled)"
            ),
        )
    job = _load_job(job_id) or {}
    author = _resolve_author(job)
    video_id = _parse_source(job.get("url", ""))["video_id"]
    download_name = f"{_safe_slug(author)}_{_safe_slug(video_id)}.mp3"
    return FileResponse(audio_path, media_type="audio/mpeg", filename=download_name)


def _refresh_metadata_sync(url: str) -> tuple[float, str | None, dict]:
    """Re-poll yt-dlp metadata WITHOUT downloading. Mirrors the handle-picker
    AND the full metrics shape (incl. tags/description) of _download_video,
    so refresh-metrics does not silently truncate already-captured fields."""
    ydl_opts = {"skip_download": True, "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    duration = float(info.get("duration") or 0)
    uploader = next(
        (
            v
            for v in (info.get("uploader_id"), info.get("uploader"), info.get("channel"))
            if v and not str(v).isdigit()
        ),
        None,
    )
    raw_tags = info.get("tags") or []
    tags = [str(t).lstrip("#").strip() for t in raw_tags if str(t).strip()]
    description = info.get("description") or ""
    metrics = {
        "views": info.get("view_count"),
        "likes": info.get("like_count"),
        "comments": info.get("comment_count"),
        "shares": info.get("repost_count"),
        "tags": tags,
        "description": description,
    }
    return duration, uploader, metrics


@app.post("/jobs/{job_id}/refresh-metrics", response_model=JobResponse)
async def refresh_metrics(job_id: str):
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "done":
        raise HTTPException(status_code=400, detail="Job must be done before metrics can be refreshed")
    url = job.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Job has no URL to refresh")

    try:
        duration, uploader, metrics = await asyncio.to_thread(_refresh_metadata_sync, url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"yt-dlp metadata fetch failed: {exc}")

    updates: dict = {"metrics": metrics}
    if duration:
        updates["duration"] = duration
    if uploader:
        updates["author"] = uploader
    _update_job(job_id, **updates)
    _write_script(job_id)

    job = _load_job(job_id) or {}
    return JobResponse(job_id=job_id, **_resolve_frames(job_id, job))


def _sanitize_user_tags(raw: list[str]) -> list[str]:
    """Trim, lowercase, dedupe (preserve order), drop empties. Cap at 32 tags
    of max 64 chars each as defense-in-depth before VPS deploy."""
    seen: set[str] = set()
    out: list[str] = []
    for t in raw or []:
        if not isinstance(t, str):
            continue
        s = t.strip().lower()[:64]
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= 32:
            break
    return out


@app.patch("/jobs/{job_id}/tags", response_model=JobResponse)
async def patch_user_tags(job_id: str, payload: UserTagsRequest):
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    cleaned = _sanitize_user_tags(payload.tags)
    _update_job(job_id, user_tags=cleaned)
    # Regenerate script.txt so the USER_TAGS header line reflects the new
    # state (no-op if there's no transcript yet).
    _write_script(job_id)
    job = _load_job(job_id) or {}
    return JobResponse(job_id=job_id, **_resolve_frames(job_id, job))


@app.post("/jobs/{job_id}/save-transcript")
async def save_transcript(job_id: str, request: SaveTranscriptRequest):
    """Local-dev-only bridge into the Wiki_Claude vault's Sourcing transcript
    registry (Projects/Sourcing/tools/transcript_registry.py, mounted at
    /sourcing/tools by docker-compose.yml — absent in prod, where this
    endpoint 501s)."""
    if transcript_registry is None:
        raise HTTPException(status_code=501, detail="Sourcing registry not mounted (local dev only).")
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.get("transcript"):
        raise HTTPException(status_code=409, detail="Job has no transcript yet.")
    niche = request.niche.strip()
    if not niche:
        raise HTTPException(status_code=422, detail="niche is required.")
    try:
        video_id = transcript_registry.extract_video_id(job["url"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = transcript_registry.save(
        niche=niche,
        video_id=video_id,
        url=job["url"],
        transcript=job["transcript"],
        channel=request.channel,
        title=request.title,
        views=request.views,
    )
    if path is None:
        return {"saved": False, "reason": "already_exists"}
    return {"saved": True, "path": str(path)}


@app.get("/jobs/{job_id}/frames.zip")
async def get_frames_zip(job_id: str):
    import io
    import zipfile

    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "done":
        raise HTTPException(status_code=400, detail="Job not done yet")
    keys = job.get("frames") or []
    if not keys:
        raise HTTPException(status_code=404, detail="No frames for this job")

    def fetch_and_zip() -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            for key in keys:
                obj = s3.get_object(Bucket=R2_BUCKET, Key=key)
                name = key.split("/")[-1]
                zf.writestr(name, obj["Body"].read())
        return buf.getvalue()

    from fastapi.responses import Response

    body = await asyncio.to_thread(fetch_and_zip)
    author = _resolve_author(job)
    video_id = _parse_source(job.get("url", ""))["video_id"]
    download_name = f"{_safe_slug(author)}_{_safe_slug(video_id)}_frames.zip"
    return Response(
        content=body,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@app.get("/status/{job_id}", response_model=JobResponse)
async def get_status(job_id: str):
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(job_id=job_id, **_resolve_frames(job_id, job))


# response_model is load-bearing: job.json holds private fields (webhook_url)
# that must not leak through this open GET — JobResponse whitelists the shape.
@app.get("/jobs", response_model=list[JobResponse])
async def list_jobs():
    jobs = []
    for job_dir in sorted(TEMP_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        job_file = job_dir / "job.json"
        if not job_file.exists():
            continue
        data = json.loads(job_file.read_text())
        jobs.append({"job_id": job_dir.name, **_resolve_frames(job_dir.name, data)})
    return jobs


@app.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str):
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Only delete R2 objects if frames are R2 keys (done status)
    if job.get("status") == "done" and job.get("frames"):
        objects = [{"Key": key} for key in job["frames"]]
        s3.delete_objects(Bucket=R2_BUCKET, Delete={"Objects": objects})

    shutil.rmtree(TEMP_DIR / job_id, ignore_errors=True)


@app.get("/jobs/{job_id}/thumbnail")
async def get_thumbnail(job_id: str):
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    frames = job.get("frames", [])
    if not frames:
        raise HTTPException(status_code=404, detail="No frames available")

    status = job.get("status")

    # Local frames still on disk
    if status in ("frames_ready", "transcribing"):
        frame_path = _frames_dir(job_id) / frames[0]
        if not frame_path.exists():
            raise HTTPException(status_code=404, detail="Frame not found")
        return FileResponse(frame_path, media_type="image/jpeg")

    # R2-backed frames
    try:
        import io

        buf = io.BytesIO()
        s3.download_fileobj(R2_BUCKET, frames[0], buf)
        buf.seek(0)
        from fastapi.responses import StreamingResponse

        return StreamingResponse(buf, media_type="image/jpeg")
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Frame not found: {exc}")


@app.get("/health")
async def health():
    return {"status": "ok"}


# --- Niche Hub (lecture seule, dev local uniquement) ----------------------


@app.get("/hub")
def get_hub():
    if not VAULT_DIR.is_dir():
        raise HTTPException(status_code=404, detail="Vault non monté (dev local uniquement).")
    return niche_hub.build_hub(VAULT_DIR)


@app.get("/hub/frame/{path:path}")
def get_hub_frame(path: str):
    if not VAULT_DIR.is_dir():
        raise HTTPException(status_code=404, detail="Vault non monté.")
    frame = niche_hub.resolve_frame(VAULT_DIR / "Projects/Sourcing/frames", path)
    return FileResponse(frame)


# Prod mode: serve the React build baked into the image at /app/static.
# In dev the directory does not exist so this block is a no-op (Vite serves
# the frontend separately at :5173). MUST come AFTER all API route declarations
# — StaticFiles is a catch-all and would shadow anything below it.
_STATIC_DIR = Path("/app/static")
if _STATIC_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
