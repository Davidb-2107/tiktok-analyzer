"""Frozen channel identity and runtime-shape validation for publication."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from .manifest import _DECIMAL_CANONICAL


_SCHEMA_PATH = Path(__file__).with_name("snapshot.schema.json")
_HANDLE = re.compile(r"@[a-z0-9][a-z0-9._-]*\Z")
_CHANNEL_SCHEMES = {"handle-slug-v1", "opaque-v1"}
_PRECISIONS = {"exact", "approximate"}
_HISTORY_FIELDS = {
    "handle",
    "valid_from",
    "valid_to",
    "valid_from_precision",
    "valid_to_precision",
    "evidence",
    "declared_by",
    "declared_at",
}
_TAXONOMY_FIELDS = {"version", "styles", "mechanics", "realism_values"}
_MEASUREMENT_FIELDS = {"target_wpm", "target_duration_s", "shot_duration_s"}
_IDENTITY_FIELDS = {
    "project_id",
    "channel_id",
    "channel_id_scheme",
    "origin_handle",
    "origin_release",
    "actor",
    "evidence",
    "handle_history",
}


@lru_cache(maxsize=None)
def _schema_required(definition: str) -> frozenset[str]:
    try:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        required = schema["$defs"][definition]["required"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"checked-in snapshot schema cannot load {definition}") from error
    if not isinstance(required, list) or not all(isinstance(field, str) for field in required):
        raise RuntimeError(f"checked-in snapshot schema has invalid {definition} required fields")
    return frozenset(required)


def _require_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _require_fields(
    value: object,
    fields: set[str] | frozenset[str],
    name: str,
) -> Mapping[str, object]:
    mapping = _require_mapping(value, name)
    missing = sorted(fields - mapping.keys())
    if missing:
        raise ValueError(f"{name} is missing required fields: {', '.join(missing)}")
    return mapping


def _nonempty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _handle(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HANDLE.fullmatch(value):
        raise ValueError(f"{name} must be a canonical @handle")
    return value


def _utc(value: object, name: str, *, allow_none: bool = False) -> datetime | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} must be a UTC timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{name} must be a UTC timestamp")
    return parsed.astimezone(timezone.utc)


def _intervals_overlap(
    first: tuple[datetime, datetime | None],
    second: tuple[datetime, datetime | None],
) -> bool:
    first_start, first_end = first
    second_start, second_end = second
    if first_end is not None and second_start >= first_end:
        return False
    if second_end is not None and first_start >= second_end:
        return False
    return True


def _validated_history(record: Mapping[str, object]) -> list[tuple[str, tuple[datetime, datetime | None]]]:
    history = record["handle_history"]
    if not isinstance(history, list) or not history:
        raise ValueError("handle_history must be a non-empty array")
    intervals: list[tuple[str, tuple[datetime, datetime | None]]] = []
    for index, entry in enumerate(history):
        item = _require_fields(entry, _HISTORY_FIELDS, f"handle_history[{index}]")
        handle = _handle(item["handle"], f"handle_history[{index}].handle")
        valid_from = _utc(item["valid_from"], f"handle_history[{index}].valid_from")
        valid_to = _utc(
            item["valid_to"],
            f"handle_history[{index}].valid_to",
            allow_none=True,
        )
        if valid_to is not None and valid_to <= valid_from:
            raise ValueError(f"handle_history[{index}] valid_to must be after valid_from")
        if item["valid_from_precision"] not in _PRECISIONS:
            raise ValueError(f"handle_history[{index}].valid_from_precision is invalid")
        if item["valid_to_precision"] not in _PRECISIONS:
            raise ValueError(f"handle_history[{index}].valid_to_precision is invalid")
        _nonempty_string(item["evidence"], f"handle_history[{index}].evidence")
        _nonempty_string(item["declared_by"], f"handle_history[{index}].declared_by")
        _utc(item["declared_at"], f"handle_history[{index}].declared_at")
        intervals.append((handle, (valid_from, valid_to)))

    for index, (_, first_interval) in enumerate(intervals):
        for other_handle, second_interval in intervals[index + 1 :]:
            if _intervals_overlap(first_interval, second_interval):
                raise ValueError(
                    "handle history intervals overlap within one channel: "
                    f"{intervals[index][0]} and {other_handle}"
                )
    return intervals


def validate_channel_record(record: Mapping[str, object]) -> None:
    """Validate one frozen channel record and its UTC handle history."""
    channel = _require_fields(
        record,
        {"channel_id", "channel_id_scheme", "current_handle", "handle_history"},
        "channel record",
    )
    _nonempty_string(channel["channel_id"], "channel_id")
    if channel["channel_id_scheme"] not in _CHANNEL_SCHEMES:
        raise ValueError("channel_id_scheme is invalid")
    _handle(channel["current_handle"], "current_handle")
    intervals = _validated_history(channel)
    open_handles = [handle for handle, (_, valid_to) in intervals if valid_to is None]
    if len(open_handles) != 1:
        raise ValueError("channel record must have exactly one open handle interval")
    if channel["current_handle"] != open_handles[0]:
        raise ValueError("current_handle must project the open handle interval")


def _index_records(index: Mapping[str, object]) -> Iterator[Mapping[str, object]]:
    if not index:
        return
    if "channels" in index:
        channels = index["channels"]
        if not isinstance(channels, list):
            raise ValueError("identity index channels must be an array")
        for record in channels:
            yield _require_mapping(record, "identity index channel")
        return
    projects = index.get("projects")
    if isinstance(projects, Mapping):
        for project_id, project in projects.items():
            project_mapping = _require_mapping(project, f"identity project {project_id!r}")
            channels = project_mapping.get("channels")
            if not isinstance(channels, list):
                raise ValueError("identity project channels must be an array")
            for record in channels:
                channel = dict(_require_mapping(record, "identity index channel"))
                channel.setdefault("project_id", project_id)
                yield channel
        return
    raise ValueError("identity index must contain channels or projects")


def _record_project(record: Mapping[str, object]) -> str:
    return _nonempty_string(record.get("project_id"), "project_id")


def _identity_intervals(record: Mapping[str, object]) -> list[tuple[str, tuple[datetime, datetime | None]]]:
    channel_record = record
    if "current_handle" not in record:
        history = record.get("handle_history")
        if isinstance(history, list):
            open_entries = [
                entry
                for entry in history
                if isinstance(entry, Mapping) and entry.get("valid_to") is None
            ]
            if len(open_entries) == 1:
                channel_record = dict(record)
                channel_record["current_handle"] = open_entries[0].get("handle")
    validate_channel_record(channel_record)
    return _validated_history(channel_record)


def validate_identity_index(index: Mapping[str, object]) -> None:
    """Validate audited channel allocation records across releases."""
    index_mapping = _require_mapping(index, "identity index")
    records = list(_index_records(index_mapping))
    seen_channel_ids: set[tuple[str, str]] = set()
    handle_intervals: dict[tuple[str, str], list[tuple[str, tuple[datetime, datetime | None]]]] = {}

    for record in records:
        _require_fields(record, _IDENTITY_FIELDS, "identity index channel")
        project_id = _record_project(record)
        channel_id = _nonempty_string(record["channel_id"], "channel_id")
        key = (project_id, channel_id)
        if key in seen_channel_ids:
            raise ValueError(f"duplicate channel_id in project: {channel_id}")
        seen_channel_ids.add(key)
        _handle(record["origin_handle"], "origin_handle")
        _nonempty_string(record["origin_release"], "origin_release")
        _nonempty_string(record["actor"], "actor")
        _nonempty_string(record["evidence"], "evidence")
        intervals = _identity_intervals(record)
        if record["origin_handle"] != intervals[0][0]:
            raise ValueError("origin_handle must match the first handle history entry")
        for handle, interval in intervals:
            handle_intervals.setdefault((project_id, handle), []).append(
                (channel_id, interval)
            )

    for (project_id, handle), intervals in handle_intervals.items():
        for index, (first_channel, first_interval) in enumerate(intervals):
            for second_channel, second_interval in intervals[index + 1 :]:
                if first_channel != second_channel and _intervals_overlap(
                    first_interval, second_interval
                ):
                    raise ValueError(
                        "handle history intervals overlap across channel IDs: "
                        f"{project_id}/{handle}"
                    )


def allocate_channel_id(
    project_id: str,
    handle: str,
    index: Mapping[str, object],
) -> tuple[str, str]:
    """Allocate a frozen channel ID without parsing existing IDs."""
    project = _nonempty_string(project_id, "project_id")
    canonical_handle = _handle(handle, "handle")
    validate_identity_index(index)
    used = {
        record["channel_id"]
        for record in _index_records(index)
        if record.get("project_id") == project
    }
    handle_slug = canonical_handle[1:]
    if handle_slug not in used:
        return handle_slug, "handle-slug-v1"

    counter = 0
    while True:
        digest = hashlib.sha256(
            f"{project}\0{canonical_handle}\0{counter}".encode("utf-8")
        ).hexdigest()[:24]
        candidate = f"opaque-{digest}"
        if candidate not in used:
            return candidate, "opaque-v1"
        counter += 1


def _validate_taxonomy(value: object) -> None:
    taxonomy = _require_fields(value, _TAXONOMY_FIELDS, "taxonomy")
    if not isinstance(taxonomy["version"], str) or not taxonomy["version"]:
        raise ValueError("taxonomy.version must be a non-empty string")
    for field in ("styles", "mechanics"):
        values = taxonomy[field]
        if not isinstance(values, list) or not all(
            isinstance(item, str) and item for item in values
        ):
            raise ValueError(f"taxonomy.{field} must be an array of strings")
    realism_values = taxonomy["realism_values"]
    if not isinstance(realism_values, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in realism_values
    ):
        raise ValueError("taxonomy.realism_values must be an array of integers")


def _validate_decimal(value: object, name: str) -> None:
    if (
        not isinstance(value, str)
        or value == "-0"
        or _DECIMAL_CANONICAL.fullmatch(value) is None
    ):
        raise ValueError(f"{name} must be a canonical decimal-v1 string")


def _validate_measurements(value: object) -> None:
    inputs = _require_fields(value, _MEASUREMENT_FIELDS, "resolved_compilation_inputs")
    _validate_decimal(inputs["target_wpm"], "target_wpm")
    for field in ("target_duration_s", "shot_duration_s"):
        values = inputs[field]
        if not isinstance(values, list):
            raise ValueError(f"{field} must be a decimal-v1 array")
        if not values:
            raise ValueError(f"{field} must be a non-empty decimal-v1 array")
        for index, item in enumerate(values):
            _validate_decimal(item, f"{field}[{index}]")


def _validate_runtime_records(
    runtime: Mapping[str, object],
    project_id: str,
) -> None:
    channels = runtime["channels"]
    if not isinstance(channels, list):
        raise ValueError("runtime.channels must be an array")
    channel_ids: set[str] = set()
    for channel in channels:
        validate_channel_record(channel)
        channel_id = channel["channel_id"]
        if channel_id in channel_ids:
            raise ValueError(f"duplicate channel_id in runtime: {channel_id}")
        channel_ids.add(channel_id)

    for field in ("formulas", "cards", "mappings"):
        if not isinstance(runtime[field], list):
            raise ValueError(f"runtime.{field} must be an array")

    formula_keys: set[tuple[str, str, str]] = set()
    for index, formula in enumerate(runtime["formulas"]):
        item = _require_fields(
            formula,
            {"channel_id", "subformula_id"},
            f"runtime.formulas[{index}]",
        )
        channel_id = _nonempty_string(item["channel_id"], "formula channel_id")
        subformula_id = _nonempty_string(item["subformula_id"], "subformula_id")
        key = (project_id, channel_id, subformula_id)
        if key in formula_keys:
            raise ValueError(f"duplicate subformula identity: {key}")
        formula_keys.add(key)

    video_keys: set[tuple[str, str, str]] = set()
    for index, mapping in enumerate(runtime["mappings"]):
        item = _require_fields(
            mapping,
            {"channel_id", "video_id", "subformula_id"},
            f"runtime.mappings[{index}]",
        )
        channel_id = _nonempty_string(item["channel_id"], "mapping channel_id")
        video_id = _nonempty_string(item["video_id"], "video_id")
        _nonempty_string(item["subformula_id"], "mapping subformula_id")
        key = (project_id, channel_id, video_id)
        if key in video_keys:
            raise ValueError(f"duplicate video assignment key: {key}")
        video_keys.add(key)


def validate_runtime_payload(
    payload_or_runtime: Mapping[str, object],
    project_id: str,
) -> None:
    """Validate the T005 runtime shape plus T006 identity invariants."""
    value = _require_mapping(payload_or_runtime, "payload")
    if "runtime" in value:
        runtime = _require_mapping(value["runtime"], "runtime")
    else:
        runtime = value
    _require_fields(runtime, _schema_required("runtime"), "runtime")
    _validate_taxonomy(runtime["taxonomy"])
    _validate_runtime_records(runtime, _nonempty_string(project_id, "project_id"))
    _validate_measurements(runtime["resolved_compilation_inputs"])


__all__ = [
    "allocate_channel_id",
    "validate_channel_record",
    "validate_identity_index",
    "validate_runtime_payload",
]
