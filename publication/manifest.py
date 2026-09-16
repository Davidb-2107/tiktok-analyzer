"""Canonical snapshot manifests, payloads, and release verification."""

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any


_RELEASE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DECIMAL_SOURCE = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?\Z")
_DECIMAL_CANONICAL = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]*[1-9])?\Z")
_SUPPORTED_SCHEMA_VERSION = 1
_CANONICALIZATION_VERSION = "json-c14n-v1"
_HASH_ALGORITHM = "sha256"
_REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "canonicalization_version",
    "hash_algorithm",
    "project_id",
    "project_id_scheme",
    "release_id",
    "payload_digest",
    "provenance",
}
_REQUIRED_RUNTIME_FIELDS = {
    "taxonomy",
    "channels",
    "formulas",
    "cards",
    "mappings",
    "resolved_compilation_inputs",
}
_REQUIRED_PROVENANCE_FIELDS = {
    "vault_commit",
    "builder_version",
    "taxonomy_module_digest",
    "module_digests",
    "sot_versions",
    "voice_profile_digest",
    "identity_history",
    "build_freshness",
}


def canonical_manifest_bytes(manifest: Mapping[str, object]) -> bytes:
    """Validate and return canonical json-c14n-v1 bytes for a manifest."""
    _validate_manifest(manifest)
    return canonical_json_bytes(manifest)


def canonical_json_bytes(value: object) -> bytes:
    """Return canonical json-c14n-v1 bytes for any supported JSON value."""
    try:
        return _canonical_value(value)
    except (TypeError, UnicodeError, ValueError) as error:
        raise ValueError(f"value is not json-c14n-v1: {error}") from error


def canonical_payload_bytes(payload: Mapping[str, object]) -> bytes:
    """Return canonical json-c14n-v1 bytes for the runtime-only payload."""
    _validate_payload(payload)
    return canonical_json_bytes(payload)


def canonical_decimal_string(value: object) -> str:
    """Normalize an exact decimal source to the decimal-v1 text form."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("decimal-v1 rejects binary float input")
    if isinstance(value, str):
        if not _DECIMAL_SOURCE.fullmatch(value):
            raise ValueError("decimal-v1 input must not use an exponent or leading zero")
        try:
            decimal = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("invalid decimal-v1 input") from error
    elif isinstance(value, (int, Decimal)):
        decimal = Decimal(value)
    else:
        raise ValueError("decimal-v1 requires an int, str, or Decimal")
    if not decimal.is_finite():
        raise ValueError("decimal-v1 rejects NaN and infinity")
    if decimal == 0:
        return "0"
    text = format(decimal, "f")
    if "." in text:
        whole, fractional = text.split(".", 1)
        text = whole + ("." + fractional.rstrip("0") if fractional.rstrip("0") else "")
    if not _DECIMAL_CANONICAL.fullmatch(text):
        raise ValueError("decimal-v1 output is not canonical")
    return text


def parse_manifest_bytes(data: bytes) -> Mapping[str, object]:
    """Parse and validate stored canonical manifest.json bytes."""
    manifest = _read_canonical_json(data, "manifest")
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be a JSON object")
    _validate_manifest(manifest)
    return manifest


def payload_digest(payload: bytes) -> str:
    """Return the SHA-256 digest of exact canonical payload.json bytes."""
    _read_canonical_json(payload, "payload")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def release_id_for(manifest: Mapping[str, object]) -> str:
    """Address a manifest without including its self-referential release ID."""
    _validate_manifest(manifest)
    addressed_manifest = dict(manifest)
    del addressed_manifest["release_id"]
    return f"sha256:{hashlib.sha256(canonical_json_bytes(addressed_manifest)).hexdigest()}"


def verify_release(release_id: str, manifest: Mapping[str, object] | bytes, payload: bytes) -> None:
    """Fail closed unless the pinned release, manifest, and payload agree."""
    if isinstance(manifest, bytes):
        manifest = parse_manifest_bytes(manifest)
    else:
        _validate_manifest(manifest)
    if not isinstance(release_id, str) or not _RELEASE_ID.fullmatch(release_id):
        raise ValueError("release ID is not canonical sha256:<lowercase-hex>")

    calculated_release_id = release_id_for(manifest)
    if release_id != calculated_release_id:
        raise ValueError("release ID does not match manifest")
    if manifest["release_id"] != calculated_release_id:
        raise ValueError("manifest release_id does not match manifest")

    _read_canonical_json(payload, "payload")
    if manifest["payload_digest"] != payload_digest(payload):
        raise ValueError("payload digest does not match manifest")


def _validate_manifest(manifest: Mapping[str, object]) -> None:
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be a mapping")
    if "runtime" in manifest:
        raise ValueError("manifest must not duplicate runtime; use payload.json")
    _require_fields(manifest, _REQUIRED_MANIFEST_FIELDS, "manifest")
    if manifest["schema_version"] != _SUPPORTED_SCHEMA_VERSION:
        raise ValueError(f"unsupported schema version: {manifest['schema_version']!r}")
    if manifest["canonicalization_version"] != _CANONICALIZATION_VERSION:
        raise ValueError("unsupported canonicalization version")
    if manifest["hash_algorithm"] != _HASH_ALGORITHM:
        raise ValueError("unsupported hash algorithm")
    if not isinstance(manifest["project_id"], str) or not isinstance(manifest["project_id_scheme"], str):
        raise ValueError("project identity fields must be strings")
    for field in ("release_id", "payload_digest"):
        if not isinstance(manifest[field], str) or not _RELEASE_ID.fullmatch(manifest[field]):
            raise ValueError(f"{field} is not canonical sha256:<lowercase-hex>")
    _require_fields(manifest["provenance"], _REQUIRED_PROVENANCE_FIELDS, "provenance")
    canonical_json_bytes(manifest)


def _validate_payload(payload: Mapping[str, object]) -> None:
    if not isinstance(payload, Mapping) or set(payload) != {"runtime"}:
        raise ValueError("payload must contain only the runtime object")
    runtime = payload["runtime"]
    _require_fields(runtime, _REQUIRED_RUNTIME_FIELDS, "runtime")
    resolved_inputs = runtime["resolved_compilation_inputs"]
    if not isinstance(resolved_inputs, Mapping):
        raise ValueError("resolved_compilation_inputs must be a mapping")
    if "target_wpm" in resolved_inputs:
        _require_canonical_decimal(resolved_inputs["target_wpm"], "target_wpm")
    for field in ("target_duration_s", "shot_duration_s"):
        if field not in resolved_inputs:
            continue
        values = resolved_inputs[field]
        if not isinstance(values, list):
            raise ValueError(f"{field} must be a decimal-v1 array")
        for index, value in enumerate(values):
            _require_canonical_decimal(value, f"{field}[{index}]")


def _require_canonical_decimal(value: object, path: str) -> None:
    if not isinstance(value, str) or value == "-0" or not _DECIMAL_CANONICAL.fullmatch(value):
        raise ValueError(f"{path} must be a canonical decimal-v1 string")


def _require_fields(value: object, fields: set[str], name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    missing = sorted(fields - value.keys())
    if missing:
        raise ValueError(f"{name} is missing required fields: {', '.join(missing)}")


def _canonical_value(value: Any) -> bytes:
    if value is None:
        return b"null"
    if value is True:
        return b"true"
    if value is False:
        return b"false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value).encode("ascii")
    if isinstance(value, str):
        return _json_string(unicodedata.normalize("NFC", value))
    if isinstance(value, list):
        return b"[" + b",".join(_canonical_value(item) for item in value) + b"]"
    if isinstance(value, Mapping):
        items: list[tuple[bytes, bytes, bytes]] = []
        seen: set[str] = set()
        for key, item in value.items():
            if not isinstance(key, str) or not key.isascii():
                raise ValueError("object keys must be ASCII strings")
            key = unicodedata.normalize("NFC", key)
            if key in seen:
                raise ValueError(f"duplicate key: {key!r}")
            seen.add(key)
            items.append((key.encode("utf-8"), _json_string(key), _canonical_value(item)))
        items.sort(key=lambda pair: pair[0])
        return b"{" + b",".join(key + b":" + item for _, key, item in items) + b"}"
    raise ValueError(f"unsupported JSON value: {type(value).__name__}")


def _json_string(value: str) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _read_canonical_json(data: bytes, name: str) -> object:
    if not isinstance(data, bytes):
        raise ValueError(f"{name} must be bytes")
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_int=_parse_integer,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
        canonical = canonical_json_bytes(value)
    except (UnicodeError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} is not canonical JSON: {error}") from error
    if canonical != data:
        raise ValueError(f"{name} bytes are not canonical")
    if name == "payload":
        _validate_payload(value)
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key!r}")
        result[key] = value
    return result


def _parse_integer(raw: str) -> int:
    if raw == "-0":
        raise ValueError("negative zero is forbidden")
    return int(raw)


def _reject_number(raw: str) -> object:
    raise ValueError(f"JSON number is forbidden: {raw}")
