"""Explicit local/release snapshot source adapters."""

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping

from publication.identity import validate_runtime_payload
from publication.manifest import parse_manifest_bytes, verify_release


_RELEASE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class SourceContext:
    kind: str
    value: str


@dataclass(frozen=True)
class SnapshotSource:
    context: SourceContext
    manifest: Mapping[str, object]
    payload_bytes: bytes
    runtime: Mapping[str, object]


def parse_source_context(value: str) -> SourceContext:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("source context is required (local:<path> or release:<release_id>)")
    kind, separator, raw_value = value.partition(":")
    if not separator or not raw_value.strip():
        raise ValueError("source context must be local:<path> or release:<release_id>")
    if kind == "local":
        return SourceContext(kind, raw_value)
    if kind == "release" and _RELEASE_ID.fullmatch(raw_value):
        return SourceContext(kind, raw_value)
    raise ValueError("source context must be local:<path> or release:<release_id>")


def resolve_source(
    context: SourceContext,
    *,
    release_root: str | Path | None = None,
) -> SnapshotSource:
    if not isinstance(context, SourceContext):
        raise TypeError("resolve_source requires parse_source_context(value)")
    if context.kind == "local":
        directory = Path(context.value)
    elif context.kind == "release":
        if release_root is None:
            raise ValueError("release_root is required for release source contexts")
        directory = Path(release_root) / "sha256" / context.value.removeprefix("sha256:")
    else:
        raise ValueError("unknown source context kind")

    source = _read_snapshot(context, directory)
    if context.kind == "release" and source.manifest["release_id"] != context.value:
        raise ValueError("release source context does not match manifest release_id")
    return source


def _read_snapshot(context: SourceContext, directory: Path) -> SnapshotSource:
    try:
        manifest_bytes = (directory / "manifest.json").read_bytes()
        payload_bytes = (directory / "payload.json").read_bytes()
    except OSError as exc:
        raise ValueError(f"source snapshot is unavailable: {directory}") from exc

    manifest = parse_manifest_bytes(manifest_bytes)
    verify_release(manifest["release_id"], manifest, payload_bytes)
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("payload is not valid UTF-8 JSON") from exc
    validate_runtime_payload(payload, project_id=manifest["project_id"])
    runtime = payload["runtime"]
    _reject_transcript_verbatim(runtime)
    _decode_measurements(runtime)
    return SnapshotSource(context, manifest, payload_bytes, runtime)


def _decode_measurements(runtime: Mapping[str, object]) -> None:
    inputs = runtime["resolved_compilation_inputs"]
    for field in ("target_wpm", "target_duration_s", "shot_duration_s"):
        value = inputs[field]
        if isinstance(value, list):
            inputs[field] = [_decimal_number(item, field) for item in value]
        else:
            inputs[field] = _decimal_number(value, field)


def _decimal_number(value: object, field: str) -> float:
    try:
        decimal = Decimal(value) if isinstance(value, str) else None
    except InvalidOperation as exc:
        raise ValueError(f"{field} is not a decimal-v1 value") from exc
    if decimal is None or not decimal.is_finite():
        raise ValueError(f"{field} is not a decimal-v1 value")
    return float(decimal)


def _reject_transcript_verbatim(value: object, path: str = "runtime") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if "transcript" in key.casefold():
                raise ValueError(f"transcript verbatim is forbidden in runtime payload ({path}.{key})")
            _reject_transcript_verbatim(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_transcript_verbatim(nested, f"{path}[{index}]")
