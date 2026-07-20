"""Hermetic tests for /channel/top order param.
main.py needs R2 env at import -> stub it (same pattern as test_guards.py).
"""

import asyncio
import os

import pytest

os.environ.setdefault("R2_ENDPOINT", "https://test.invalid")
for k in ("R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
    os.environ.setdefault(k, "test")
pytest.importorskip("faster_whisper")
pytest.importorskip("yt_dlp")

import main  # noqa: E402
from fastapi import HTTPException  # noqa: E402

N_ENTRIES = 60


def _listing_entries():
    """Channel listing order = newest first (descending video ids).
    Views deliberately NOT monotonic so order-preservation is observable."""
    return [
        {
            "url": f"https://www.tiktok.com/@x/video/{N_ENTRIES - i}",
            "title": f"v{N_ENTRIES - i}",
            "view_count": (i * 37) % 1000,
            "duration": 60,
        }
        for i in range(N_ENTRIES)
    ]


class _FakeYDL:
    last_opts = None

    def __init__(self, opts):
        _FakeYDL.last_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        return {"entries": _listing_entries()}


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(main.yt_dlp, "YoutubeDL", _FakeYDL)
    # fresh semaphore per test: asyncio.run() creates a new loop each call
    monkeypatch.setattr(main, "_ENUM_SEMAPHORE", asyncio.Semaphore(2))


def _call(**kw):
    return asyncio.run(main.channel_top(**kw))


def test_default_order_views_sorted_and_capped_at_20(patched):
    out = _call(url="https://www.tiktok.com/@x", n=99)
    views = [v["views"] for v in out["top"]]
    assert len(out["top"]) == 20  # legacy clamp intact
    assert views == sorted(views, reverse=True)
    assert _FakeYDL.last_opts["playlistend"] == 200  # legacy window intact


def test_recent_preserves_listing_order(patched):
    out = _call(url="https://www.tiktok.com/@x", n=5, order="recent")
    urls = [v["url"] for v in out["top"]]
    assert urls == [f"https://www.tiktok.com/@x/video/{N_ENTRIES - i}" for i in range(5)]


def test_recent_allows_n_50_and_narrows_playlistend(patched):
    out = _call(url="https://www.tiktok.com/@x", n=99, order="recent")
    assert len(out["top"]) == 50
    assert _FakeYDL.last_opts["playlistend"] == 50


def test_invalid_order_rejected(patched):
    with pytest.raises(HTTPException) as exc:
        _call(url="https://www.tiktok.com/@x", order="sideways")
    assert exc.value.status_code == 422
