"""Hermetic tests for POST /watch/channels (n8n channel-watch webhook proxy).
main.py needs R2 env at import -> stub it (same pattern as test_guards.py).
"""

import asyncio
import json
import os
import urllib.error

import pytest

os.environ.setdefault("R2_ENDPOINT", "https://test.invalid")
for k in ("R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
    os.environ.setdefault(k, "test")
pytest.importorskip("faster_whisper")
pytest.importorskip("yt_dlp")

import main  # noqa: E402
from fastapi import HTTPException  # noqa: E402


class _FakeResp:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._body).encode()


def _call(url="https://www.tiktok.com/@x", label="", niche=""):
    return asyncio.run(main.watch_channel(main.WatchChannelRequest(url=url, label=label, niche=niche)))


def test_invalid_domain_rejected():
    with pytest.raises(HTTPException) as exc:
        _call(url="https://evil.example.com/@x")
    assert exc.value.status_code == 422


def test_missing_config_returns_503(monkeypatch):
    monkeypatch.delenv("VEILLE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VEILLE_WEBHOOK_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc:
        _call()
    assert exc.value.status_code == 503
    assert exc.value.detail == "channel watch not configured"


def test_success_relays_webhook_body(monkeypatch):
    monkeypatch.setenv("VEILLE_WEBHOOK_URL", "https://n8n.example.com/webhook/veille")
    monkeypatch.setenv("VEILLE_WEBHOOK_SECRET", "s3cret")

    captured = {}

    def fake_urlopen(req, timeout=15):
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data)
        return _FakeResp({"ok": True, "created": True})

    monkeypatch.setattr(main.urllib.request, "urlopen", fake_urlopen)

    out = _call(url="https://www.tiktok.com/@x", label="X channel", niche="psycho")
    assert out == {"ok": True, "created": True}
    assert captured["headers"]["X-veille-key"] == "s3cret"
    assert captured["body"] == {"url": "https://www.tiktok.com/@x", "label": "X channel", "niche": "psycho"}


def test_webhook_error_status_returns_502(monkeypatch):
    monkeypatch.setenv("VEILLE_WEBHOOK_URL", "https://n8n.example.com/webhook/veille")
    monkeypatch.setenv("VEILLE_WEBHOOK_SECRET", "s3cret")

    def fake_urlopen(req, timeout=15):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", None, None)

    monkeypatch.setattr(main.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(HTTPException) as exc:
        _call()
    assert exc.value.status_code == 502
