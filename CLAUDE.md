# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Project

**Full stack (recommended):**
```bash
docker-compose up
```
- Backend: `http://localhost:8000` (FastAPI + uvicorn with hot-reload)
- Frontend: `http://localhost:5173` (Vite dev server)

**Backend only (outside Docker):**
```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend only (outside Docker):**
```bash
cd frontend && npm run dev
```

**Frontend build:**
```bash
cd frontend && npm run build
```

There are no test or lint scripts configured.

## Architecture

**Backend** (`backend/main.py`) is a single-file FastAPI app. It manages video processing jobs asynchronously: downloads TikTok/YouTube videos via yt-dlp, extracts frames with ffmpeg, uploads frames to Cloudflare R2, and fetches captions. If captions are absent, it can transcribe audio locally with `faster-whisper` (model configurable via `WHISPER_MODEL`, default `medium`, int8 on CPU).

**Frontend** (`frontend/src/App.jsx`) is a React SPA. It submits a URL, then polls `GET /status/{job_id}` every 500ms to drive UI state until the job reaches `done` or `error`.

**Job state machine:**
```
pending → downloading → extracting → frames_ready → done (captions found)
                                                  → transcribing → done
                                                  → error (at any stage)
```
Transcription is automatic when no captions are found in the source — no manual gate. The job blocks on Whisper for ~2-3× realtime on CPU/int8/medium.

Job metadata is persisted to `temp/{job_id}/job.json`. The `temp/` directory is Docker-volume-mounted so it survives container restarts.

## Key API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/analyze` | Create job (`{ url, fps }`) |
| `GET` | `/status/{job_id}` | Poll job status |
| `GET` | `/jobs` | List all jobs |
| `DELETE` | `/jobs/{job_id}` | Delete job + R2 objects |
| `GET` | `/frames/{job_id}/local/{frame_name}` | Serve local frame during processing |
| `GET` | `/jobs/{job_id}/thumbnail` | First frame (local or R2 presigned URL) |
| `GET` | `/health` | Health check |

## Frame Serving

During processing, frames are served locally via `/frames/{job_id}/local/{frame_name}`. After upload completes, the frontend switches to presigned R2 URLs. The `FrameGallery` component handles both URL shapes.

## Environment Variables

All secrets live in `.env` (not committed). Required keys:

```
R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
R2_BUCKET, R2_ENDPOINT
ALLOWED_ORIGIN          # CORS origin (use * for dev)
MAX_CONCURRENT_JOBS     # Default: 2
WHISPER_MODEL           # faster-whisper model (tiny/base/small/medium/large-v3). Default: medium
WHISPER_DEVICE          # cpu or cuda. Default: cpu
WHISPER_COMPUTE_TYPE    # int8 (CPU recommended) or float16 (GPU). Default: int8
HF_CACHE_DIR            # Host path mounted as /root/.cache/huggingface to reuse downloaded models
```

## Frontend Polling & Error Handling

The frontend retries failed status polls up to 5 times before disconnecting. Polling interval is 500ms. This logic lives in `App.jsx`.
