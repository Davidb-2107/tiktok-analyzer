"""Explicit snapshot-backed Hub configuration and route registration."""

import os
from dataclasses import dataclass
from typing import Mapping

from fastapi import HTTPException
from fastapi.responses import FileResponse
from hub_read_model import project_runtime
from media_store import MediaStore
from publication.source import SnapshotSource, parse_source_context, resolve_source


@dataclass(frozen=True)
class HubService:
    source: SnapshotSource
    read_model: Mapping[str, object]
    media: MediaStore


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required when the Hub route is enabled")
    return value


def load_hub_service(environ: Mapping[str, str] | None = None) -> HubService | None:
    environ = os.environ if environ is None else environ
    enabled = environ.get("HUB_ROUTE_ENABLED", "false").strip().lower()
    if enabled in {"false", "0", "no"}:
        return None
    if enabled not in {"true", "1", "yes"}:
        raise ValueError("HUB_ROUTE_ENABLED must be true or false")

    profile = _required(environ, "HUB_PROFILE")
    if profile not in {"production", "local"}:
        raise ValueError("HUB_PROFILE must be production or local")
    context = parse_source_context(_required(environ, "HUB_SOURCE_CONTEXT"))
    if profile == "production" and context.kind != "release":
        raise ValueError("production Hub requires a release source context")
    release_root = environ.get("HUB_RELEASE_ROOT", "").strip() or None
    if context.kind == "release" and release_root is None:
        raise ValueError("HUB_RELEASE_ROOT is required for release source contexts")
    media_root = _required(environ, "HUB_MEDIA_ROOT")

    source = resolve_source(context, release_root=release_root)
    read_model = {
        "release_id": source.manifest["release_id"],
        **project_runtime(source.runtime),
    }
    return HubService(
        source=source,
        read_model=read_model,
        media=MediaStore(media_root),
    )


def register_hub_routes(app, service: HubService | None) -> None:
    if service is None:
        return

    @app.get("/hub")
    def get_hub():
        return service.read_model

    @app.get("/hub/frame/{frame_id}")
    def get_hub_frame(frame_id: str):
        try:
            frame = service.media.resolve(frame_id)
        except (FileNotFoundError, ValueError):
            raise HTTPException(status_code=404, detail="Frame introuvable.") from None
        return FileResponse(frame)
