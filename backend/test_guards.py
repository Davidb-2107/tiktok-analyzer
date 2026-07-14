"""Hermetic pytest for the /analyze input guards added with queue/batch/webhook.
main.py needs R2 env at import -> stub it (same pattern as test_ocr.py).
"""

import os

import pytest

os.environ.setdefault("R2_ENDPOINT", "https://test.invalid")
for k in ("R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
    os.environ.setdefault(k, "test")
pytest.importorskip("faster_whisper")
pytest.importorskip("yt_dlp")

from fastapi import HTTPException  # noqa: E402
from main import _normalize_project, _validate_webhook_url  # noqa: E402


def _fake_getaddrinfo(ips):
    return lambda host, port: [(None, None, None, None, (ip, 0)) for ip in ips]


def test_webhook_url_accepts_public(monkeypatch):
    import main

    monkeypatch.setattr(
        main.socket, "getaddrinfo", _fake_getaddrinfo(["93.184.216.34"])
    )
    _validate_webhook_url("https://n8n.example.com/webhook/abc")  # must not raise
    _validate_webhook_url("http://93.184.216.34/hook")  # public IP literal


def test_webhook_url_rejects_private_resolution(monkeypatch):
    """A public-looking hostname resolving to an internal IP must be rejected
    (the DNS trick is the whole point of the resolve-time SSRF guard)."""
    import main

    monkeypatch.setattr(main.socket, "getaddrinfo", _fake_getaddrinfo(["172.17.0.1"]))
    with pytest.raises(HTTPException) as exc:
        _validate_webhook_url("https://innocent-looking.com/hook")
    assert exc.value.status_code == 422


def test_webhook_url_rejects_unresolvable(monkeypatch):
    """DNS failure = fail closed."""
    import socket as _socket

    import main

    def boom(host, port):
        raise _socket.gaierror("NXDOMAIN")

    monkeypatch.setattr(main.socket, "getaddrinfo", boom)
    with pytest.raises(HTTPException) as exc:
        _validate_webhook_url("https://does-not-exist.invalid/hook")
    assert exc.value.status_code == 422


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/x",
        "not a url",
        "http://localhost:5678/hook",
        "http://myhost.local/hook",
        "http://127.0.0.1/hook",
        "http://10.0.0.5/hook",
        "http://192.168.1.10/hook",
        "http://172.16.0.1/hook",
    ],
)
def test_webhook_url_rejects_internal(url):
    with pytest.raises(HTTPException) as exc:
        _validate_webhook_url(url)
    assert exc.value.status_code == 422


def test_adaptive_fps_long_video_stays_near_target():
    from main import _adaptive_fps

    # 25min master: target 100 frames -> fps ~0.067, floor must not inflate it
    assert _adaptive_fps(1500) * 1500 == pytest.approx(100, abs=1)
    # short clip unchanged: 30 frames over 15s
    assert _adaptive_fps(15) * 15 == pytest.approx(30, abs=1)
    assert _adaptive_fps(0) == 1.0


def test_normalize_project():
    assert _normalize_project(None) is None
    assert _normalize_project("  Psycho ") == "psycho"
    assert _normalize_project("") is None
    with pytest.raises(HTTPException):
        _normalize_project("nope")
