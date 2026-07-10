---
name: analyze-video
description: Use when the user pastes a TikTok/YouTube/Instagram URL and asks a question about it, wants a summary, hook breakdown, or bug diagnosis from the video — invoke as /analyze-video <url> [question] [--start S] [--end E]. Downloads frames + transcript + on-screen overlay text via the TikTok Analyzer API and hands the frames to Claude's own vision.
requires:
  - python >= 3.8 (stdlib only, no pip install)
  - network access to https://tiktok-analyzer.hen8n.com (or TT_BASE_URL override)
---

# analyze-video

Give Claude the ability to watch a TikTok/YouTube/Instagram video: paste a URL and a
question, get frames read as images plus the spoken transcript and on-screen
overlay text (captions burned into the video), grounded in what's actually
on screen — not a guess from the title.

Backed by the TikTok Analyzer API (`https://tiktok-analyzer.hen8n.com`): server-side
frame extraction, local Whisper transcription, and OCR of on-screen text — so this
skill itself stays a thin HTTP client with zero dependencies.

## Invocation

```
/analyze-video <url> [question]
/analyze-video <url> [question] --start 5 --end 10
```

- `<url>`: a TikTok/YouTube/Instagram link (yt-dlp-supported).
- `[question]`: optional — what to answer about the video. If omitted, do open
  analysis (summarize, describe structure, whatever the surrounding conversation implies).
- `--start S --end E`: optional — focus on that time window (seconds) instead of the
  whole video. Use this when the user names a moment ("around the 5s mark", "the hook",
  "the last 10 seconds") — it's denser-sampled and much cheaper than scanning the whole clip.

## Steps

1. Run the helper script:
   ```
   python "<this skill's dir>/analyze.py" "<url>" [--start S] [--end E]
   ```
   It prints a `manifest.json` path on stdout on success, or `error: ...` on stderr
   and a nonzero exit code on failure (bad URL, job error, timeout — report this to
   the user rather than retrying blindly).
2. Read the manifest JSON (`transcript`, `overlay_text`, `hook_overlay_text`, `frames`
   — a list of local image file paths, `duration`, `start_s`/`end_s`).
3. **`Read` every frame path in the `frames` list** — this is the "watch the video" step;
   Claude Code's `Read` tool renders JPEGs as images directly in context.
4. Answer the user's question (or do the requested open-ended analysis) grounded in
   what was seen in the frames and read in the transcript/overlay text — not from the
   URL, title, or prior knowledge of the content.
5. Clean up: delete the scratch directory printed by the script (`rm -rf <dir>`) once
   you're done answering — unless the user is likely to ask a follow-up in the same
   turn, in which case leave it until the conversation moves on.

## Notes

- No `pip install` needed — `analyze.py` uses only the Python standard library.
- If the server enforces an API key, set `TT_API_KEY` in the environment before invoking.
- `--start`/`--end` skip the full-video pass server-side (denser sampling of just that
  window) and do not include the opening-seconds "hook" overlay pass — expect
  `hook_overlay_text` to be `null` when a window was requested.
- This is a copy of the skill versioned in the TikTok Analyzer repo
  (`skills/analyze-video/`). To use it from any Claude Code session regardless of
  which repo is open, copy or symlink this folder to `~/.claude/skills/analyze-video/`.
