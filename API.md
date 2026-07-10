# TikTok Analyzer — API Usage (for another session)

**The service is LIVE and public.** Any session can analyze a TikTok/YouTube video
end-to-end (download → frame extraction → R2 upload → transcription) by calling the
REST API. No auth required (Cloudflare Access is bypassed for this hostname).

- **Base URL (prod):** `https://tiktok-analyzer.hen8n.com`
- **Base URL (local dev):** `http://localhost:8000`

## Flow

1. `POST /analyze` with `{ "url": "<tiktok-or-youtube-url>" }` → returns a `job_id`.
   `fps` is optional — omit it to let the server pick an adaptive frame budget
   from the video's duration (denser for short videos, capped for long ones).
   Optionally add `start_s`/`end_s` to analyze only a specific window (see below).
2. Poll `GET /status/{job_id}` until `status` is `done` or `error`.
3. Read `transcript`, `segments`, `frames` from the final status payload.

State machine: `pending → downloading → extracting → frames_ready → (done | transcribing → done | error)`.
Transcription is automatic when the source has no captions (local faster-whisper, ~1–3× realtime on CPU).

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/analyze` | Create a job. Body: `{ url, fps?, start_s?, end_s? }`. `fps` omitted → adaptive. `start_s`/`end_s` → analyze only that window (denser sampling, skips the hook pass). |
| `GET`  | `/status/{job_id}` | Poll job state (see schema below). |
| `GET`  | `/jobs` | List all jobs. |
| `DELETE` | `/jobs/{job_id}` | Delete job + its R2 objects. |
| `GET`  | `/jobs/{job_id}/thumbnail` | First frame (jpeg). |
| `GET`  | `/jobs/{job_id}/audio.mp3` | Extracted audio (mp3, retained after transcription). |
| `GET`  | `/health` | `{"status":"ok"}`. |

## `/status/{job_id}` response schema

```jsonc
{
  "job_id":    "uuid",
  "status":    "pending|downloading|extracting|frames_ready|transcribing|done|error",
  "url":       "source url",
  "frames":    ["https://<r2-presigned-url>.jpg", ...],  // presigned R2 URLs once uploaded
  "duration":  88,                                        // seconds
  "transcript":"full text...",
  "segments":  [ { "start": 0, "end": 1.78, "text": "...", "words": [ { "start", "end", "word" } ] } ],
  // On-screen overlay text (OCR, RapidOCR PP-OCRv5 latin) — the visual parallel of the
  // audio transcript. Both null when no overlay text was detected (or OCR failed):
  // consumers must read them absent-safe (`j.overlay_text ?? null`, `j.overlay_segments ?? []`).
  "overlay_text":     "on-screen text, one deduplicated caption per line",
  "overlay_segments": [ { "start": 1.0, "end": 5.0, "text": "POV: ...", "confidence": 0.94 } ],
  // Hook microscope: a denser 2fps OCR pass over the first 5s (HOOK_FPS / HOOK_WINDOW_S),
  // where a video wins or loses attention — catches overlay captions that flash <1s and
  // are missed by the 1fps main pass. Same shape/absent-safe rules as overlay_* (both null
  // when nothing detected). Timestamps are seconds within the hook window.
  "hook_overlay_text":     "opening on-screen text, one caption per line",
  "hook_overlay_segments": [ { "start": 0.5, "end": 2.0, "text": "wait for it...", "confidence": 0.91 } ],
  "error":     null,                                      // string when status == "error"
  "project":   null,
  "user_tags": [],
  "fps":       1.2,                                       // resolved fps (explicit or adaptive)
  "start_s":   null,                                      // echoed back when a window was requested
  "end_s":     null
}
```

## Adaptive frame budget + dedup

Omit `fps` and the server picks a target frame count from the probed duration
(~30 frames for ≤30s clips, up to ~100 for 10min+), then derives `fps` from
it. Near-duplicate consecutive frames (e.g. a held title card) are dropped
before OCR/upload — `frames` in the final payload may be fewer than
`fps * duration`. Explicit `fps` still works exactly as before and is never
overridden.

## Focused time window

Pass `start_s`/`end_s` to analyze only that slice of the video, sampled
denser (`WINDOW_FPS`, default 2fps) than the main pass. `duration` in the
response always reports the FULL source video length, not the window — the
window is echoed back separately via `start_s`/`end_s`. A windowed job skips
the full-video pass entirely and does **not** run the hook-microscope pass
(`hook_overlay_text`/`hook_overlay_segments` are `null`) since the requested
window already is the dense pass.

## Copy-paste client (Node, no deps)

```js
const BASE = "https://tiktok-analyzer.hen8n.com";
const API_KEY = process.env.TT_API_KEY || ""; // set only if the server enforces a key

async function analyze(url, { fps, start_s, end_s, timeoutMs = 600000 } = {}) {
  const r = await fetch(`${BASE}/analyze`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
    },
    body: JSON.stringify({ url, fps, start_s, end_s }),
  });
  if (!r.ok) throw new Error(`analyze failed: ${r.status}`);
  const { job_id } = await r.json();

  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const j = await (await fetch(`${BASE}/status/${job_id}`)).json();
    if (j.status === "done")  return j;                 // -> j.transcript, j.segments, j.frames
    if (j.status === "error") throw new Error(j.error || "job error");
    await new Promise(s => setTimeout(s, 5000));
  }
  throw new Error("timeout");
}

// usage:
// const res = await analyze("https://www.tiktok.com/@user/video/123...");
// console.log(res.transcript, res.segments.length, res.frames.length);
```

## Notes

- `frames` are local paths (`/frames/{job_id}/local/{name}`) during processing, then switch to
  absolute presigned R2 URLs after upload — handle both shapes.
- Transcription language is auto-detected (e.g. French).
- Audio is retained: `GET /jobs/{job_id}/audio.mp3` works after the job is done.
- **Auth:** if the server sets `API_KEY`, mutating requests (`POST /analyze`, `DELETE`)
  require header `X-API-Key: <key>`; `GET` reads stay open. With no `API_KEY` set the
  endpoint is fully open.
- **Input guards:** `/analyze` only accepts hosts in the allowlist (`tiktok.com`,
  `youtube.com`, `youtu.be` by default) and rejects videos longer than the duration cap
  (`MAX_VIDEO_DURATION_SEC`, default 600s) — both return HTTP 422.

## Claude Code skill

`skills/analyze-video/` in this repo is a thin, stdlib-only client for this API,
packaged as a Claude Code skill: `/analyze-video <url> [question] [--start S] [--end E]`
downloads frames + transcript + overlay text locally and hands the frames to
Claude's vision to answer grounded in what's on screen. To use it from ANY
Claude Code session (not just this repo), copy or symlink the folder to
`~/.claude/skills/analyze-video/`.
