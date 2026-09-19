"""Hermetic Hub snapshot/configuration contract tests."""

from pathlib import Path

import hub
import pytest
from fastapi import FastAPI, HTTPException

from media_store import MediaStore
from test_source_context import _write_snapshot


def _payload():
    return {
        "runtime": {
            "taxonomy": {
                "version": "1.0.0",
                "styles": ["AI animation"],
                "mechanics": ["question"],
                "realism_values": [5],
            },
            "channels": [
                {
                    "channel_id": "alpha-frozen",
                    "channel_id_scheme": "opaque-v1",
                    "current_handle": "@renamed",
                    "handle_history": [
                        {
                            "handle": "@old_handle",
                            "valid_from": "2025-01-01T00:00:00Z",
                            "valid_to": "2026-01-01T00:00:00Z",
                            "valid_from_precision": "exact",
                            "valid_to_precision": "exact",
                            "evidence": "fixture-old",
                            "declared_by": "fixture",
                            "declared_at": "2025-01-01T00:00:00Z",
                        },
                        {
                            "handle": "@renamed",
                            "valid_from": "2026-01-01T00:00:00Z",
                            "valid_to": None,
                            "valid_from_precision": "exact",
                            "valid_to_precision": "approximate",
                            "evidence": "fixture-current",
                            "declared_by": "fixture",
                            "declared_at": "2026-01-01T00:00:00Z",
                        },
                    ],
                }
            ],
            "formulas": [
                {"channel_id": "alpha-frozen", "subformula_id": "alpha-main"}
            ],
            "cards": [
                {
                    "channel_id": "alpha-frozen",
                    "video_id": "video-assigned",
                    "title": "Assigned",
                    "views": 42,
                    "frame_id": "frameA123",
                    "ref": "must/not/leak.md",
                },
                {
                    "channel_id": "alpha-frozen",
                    "video_id": "video-pending",
                    "title": "Pending",
                    "views": 99,
                },
            ],
            "mappings": [
                {
                    "channel_id": "alpha-frozen",
                    "video_id": "video-assigned",
                    "subformula_id": "alpha-main",
                    "status": "assigned",
                },
                {
                    "channel_id": "alpha-frozen",
                    "video_id": "video-pending",
                    "subformula_id": "alpha-main",
                    "status": "pending",
                },
            ],
            "resolved_compilation_inputs": {
                "target_wpm": "215",
                "target_duration_s": ["62", "75"],
                "shot_duration_s": ["2.5"],
            },
        }
    }


def _env(**overrides):
    values = {
        "HUB_ROUTE_ENABLED": "true",
        "HUB_PROFILE": "production",
        "HUB_SOURCE_CONTEXT": "",
        "HUB_RELEASE_ROOT": "",
        "HUB_MEDIA_ROOT": "",
    }
    values.update(overrides)
    return values


def test_production_resolves_only_a_pinned_release_and_propagates_release_id(tmp_path):
    payload = _payload()
    manifest, _ = _write_snapshot(tmp_path / "draft", payload, project_id="niche-42")
    release_root = tmp_path / "releases"
    release_dir = release_root / "sha256" / manifest["release_id"].removeprefix("sha256:")
    _write_snapshot(release_dir, payload, project_id="niche-42")

    service = hub.load_hub_service(
        _env(
            HUB_SOURCE_CONTEXT=f"release:{manifest['release_id']}",
            HUB_RELEASE_ROOT=str(release_root),
            HUB_MEDIA_ROOT=str(tmp_path / "media"),
        )
    )

    assert service.read_model["release_id"] == manifest["release_id"]
    assert service.source.context.kind == "release"
    with pytest.raises(ValueError, match="production.*release"):
        hub.load_hub_service(
            _env(
                HUB_SOURCE_CONTEXT=f"local:{tmp_path / 'draft'}",
                HUB_MEDIA_ROOT=str(tmp_path / "media"),
            )
        )


def test_production_resolves_the_active_release_state_over_stale_context(tmp_path):
    payload = _payload()
    manifest, _ = _write_snapshot(tmp_path / "draft", payload, project_id="niche-42")
    release_root = tmp_path / "releases"
    release_dir = release_root / "sha256" / manifest["release_id"].removeprefix("sha256:")
    _write_snapshot(release_dir, payload, project_id="niche-42")
    state_path = tmp_path / "state" / "active-release"
    state_path.parent.mkdir()
    state_path.write_text(manifest["release_id"] + "\n", encoding="ascii")

    service = hub.load_hub_service(
        _env(
            HUB_SOURCE_CONTEXT="release:sha256:" + "b" * 64,
            HUB_ACTIVE_RELEASE_PATH=str(state_path),
            HUB_RELEASE_ROOT=str(release_root),
            HUB_MEDIA_ROOT=str(tmp_path / "media"),
        )
    )

    assert service.source.context.value == manifest["release_id"]
    assert service.read_model["release_id"] == manifest["release_id"]


def test_production_fails_closed_when_active_release_state_is_missing(tmp_path):
    with pytest.raises(ValueError, match="active release state"):
        hub.load_hub_service(
            _env(
                HUB_SOURCE_CONTEXT="release:sha256:" + "b" * 64,
                HUB_ACTIVE_RELEASE_PATH=str(tmp_path / "missing-active-release"),
                HUB_RELEASE_ROOT=str(tmp_path / "releases"),
                HUB_MEDIA_ROOT=str(tmp_path / "media"),
            )
        )


def test_local_profile_accepts_only_an_explicit_draft_context(tmp_path):
    _write_snapshot(tmp_path / "draft", _payload(), project_id="niche-42")
    service = hub.load_hub_service(
        _env(
            HUB_PROFILE="local",
            HUB_SOURCE_CONTEXT=f"local:{tmp_path / 'draft'}",
            HUB_MEDIA_ROOT=str(tmp_path / "media"),
        )
    )
    assert service.source.context.kind == "local"

    assert hub.load_hub_service(_env(HUB_ROUTE_ENABLED="false")) is None
    with pytest.raises(ValueError, match="HUB_ROUTE_ENABLED"):
        hub.load_hub_service(_env(HUB_ROUTE_ENABLED="sometimes"))


def test_projection_routes_by_frozen_channel_id_and_only_assigned_mappings(tmp_path):
    _write_snapshot(tmp_path / "draft", _payload(), project_id="niche-42")
    service = hub.load_hub_service(
        _env(
            HUB_PROFILE="local",
            HUB_SOURCE_CONTEXT=f"local:{tmp_path / 'draft'}",
            HUB_MEDIA_ROOT=str(tmp_path / "media"),
        )
    )

    assert [niche["key"] for niche in service.read_model["niches"]] == ["alpha-frozen"]
    niche = service.read_model["niches"][0]
    assert niche["nom"] == "@renamed"
    assert [video["id"] for video in niche["sourcing"]["videos"]] == ["video-assigned"]
    video = niche["sourcing"]["videos"][0]
    assert video["chaine"] == "@renamed"
    assert video["thumb"] == "frameA123"
    assert video["transcript_ref"] is None
    assert video["card_ref"] is None
    assert "@old_handle" not in str(service.read_model)


def test_enabled_hub_fails_closed_on_missing_configuration():
    for missing in ("HUB_PROFILE", "HUB_SOURCE_CONTEXT", "HUB_MEDIA_ROOT"):
        env = _env(
            HUB_SOURCE_CONTEXT="release:sha256:" + "a" * 64,
            HUB_RELEASE_ROOT="/releases",
            HUB_MEDIA_ROOT="/media",
        )
        env.pop(missing)
        with pytest.raises(ValueError, match=missing):
            hub.load_hub_service(env)


def test_media_store_rejects_path_shaped_ids_before_filesystem_access(monkeypatch, tmp_path):
    store = MediaStore(tmp_path)

    def filesystem_access_is_a_bug(_path):
        pytest.fail("invalid frame IDs must be rejected before filesystem access")

    monkeypatch.setattr(Path, "is_file", filesystem_access_is_a_bug)
    for frame_id in ("../secret", "folder/frame", r"folder\\frame", "/absolute", "C:drive", "frame.jpg"):
        with pytest.raises(ValueError, match="opaque"):
            store.resolve(frame_id)


def test_media_store_resolves_an_opaque_id_without_exposing_the_path(tmp_path):
    frame = tmp_path / "frameA123.jpg"
    frame.write_bytes(b"jpeg")

    assert MediaStore(tmp_path).resolve("frameA123") == frame


def test_route_registration_is_explicit_and_frame_errors_are_closed(monkeypatch, tmp_path):
    disabled = FastAPI()
    hub.register_hub_routes(disabled, None)
    assert "/hub" not in {route.path for route in disabled.routes}

    _write_snapshot(tmp_path / "draft", _payload(), project_id="niche-42")
    service = hub.load_hub_service(
        _env(
            HUB_PROFILE="local",
            HUB_SOURCE_CONTEXT=f"local:{tmp_path / 'draft'}",
            HUB_MEDIA_ROOT=str(tmp_path / "media"),
        )
    )
    enabled = FastAPI()
    hub.register_hub_routes(enabled, service)
    routes = {route.path: route.endpoint for route in enabled.routes}
    assert routes["/hub"]() == service.read_model

    monkeypatch.setattr(
        Path,
        "is_file",
        lambda _path: pytest.fail("path-shaped ID reached the filesystem"),
    )
    with pytest.raises(HTTPException) as exc:
        routes["/hub/frame/{frame_id}"]("../secret")
    assert exc.value.status_code == 404
