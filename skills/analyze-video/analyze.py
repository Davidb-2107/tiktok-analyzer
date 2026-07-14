#!/usr/bin/env python3
"""Thin client for the TikTok Analyzer API — no third-party deps.

POST /analyze, poll /status, download frames + transcript + overlay text into
a scratch dir, write manifest.json. Used by SKILL.md so Claude can `Read`
each frame image and reason over the transcript, mirroring how claude-video
hands frames to Claude's vision.
"""

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://tiktok-analyzer.hen8n.com"
# Cloudflare blocks the default Python-urllib/3.x UA (403 error 1010); any other value passes.
USER_AGENT = "analyze-video-skill/1.0"
POLL_INTERVAL_S = 4
TIMEOUT_S = 1800  # covers server-side queue wait (jobs may sit pending behind 2 slots)


def _request(
    method: str, url: str, api_key: str | None, body: dict | None = None
) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("content-type", "application/json")
    req.add_header("user-agent", USER_AGENT)
    if api_key:
        req.add_header("X-API-Key", api_key)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"user-agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def analyze(
    url: str,
    base_url: str,
    api_key: str | None,
    start_s: float | None,
    end_s: float | None,
    out_dir: Path,
) -> dict:
    body = {"url": url, "start_s": start_s, "end_s": end_s}
    job = _request("POST", f"{base_url}/analyze", api_key, body)
    job_id = job["job_id"]

    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    deadline = time.time() + TIMEOUT_S
    status = job
    while time.time() < deadline:
        status = _request("GET", f"{base_url}/status/{job_id}", api_key)
        if status["status"] == "error":
            raise RuntimeError(f"job {job_id} failed: {status.get('error')}")
        if status["status"] == "done":
            break
        time.sleep(POLL_INTERVAL_S)
    else:
        raise TimeoutError(f"job {job_id} did not finish within {TIMEOUT_S}s")

    frame_paths = []
    for name in status.get("frames", []):
        # Local filename (mid-processing) vs already-presigned R2 URL (done).
        src = (
            name
            if name.startswith("http")
            else f"{base_url}/frames/{job_id}/local/{name}"
        )
        dest = frames_dir / Path(name.split("?")[0]).name
        _download(src, dest)
        frame_paths.append(str(dest))

    manifest = {
        "job_id": job_id,
        "url": url,
        "duration": status.get("duration"),
        "start_s": status.get("start_s"),
        "end_s": status.get("end_s"),
        "frames": frame_paths,
        "transcript": status.get("transcript"),
        "overlay_text": status.get("overlay_text"),
        "hook_overlay_text": status.get("hook_overlay_text"),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--start", type=float, default=None, dest="start_s")
    parser.add_argument("--end", type=float, default=None, dest="end_s")
    parser.add_argument(
        "--base-url", default=os.environ.get("TT_BASE_URL", DEFAULT_BASE_URL)
    )
    parser.add_argument("--api-key", default=os.environ.get("TT_API_KEY"))
    parser.add_argument(
        "--out", default=None, help="Scratch dir (default: fresh tempdir)"
    )
    args = parser.parse_args()

    out_dir = (
        Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="analyze-video-"))
    )
    try:
        manifest = analyze(
            args.url, args.base_url, args.api_key, args.start_s, args.end_s, out_dir
        )
    except (urllib.error.URLError, RuntimeError, TimeoutError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(str(out_dir / "manifest.json"))
    print(
        f"{len(manifest['frames'])} frames downloaded to {out_dir / 'frames'}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
