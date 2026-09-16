"""Canonical snapshot-manifest validation and release identity."""

import hashlib
import json
import re
from collections.abc import Mapping


_RELEASE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SUPPORTED_SCHEMA_VERSION = 1
_CANONICALIZATION_VERSION = "json-c14n-v1"
_HASH_ALGORITHM = "sha256"
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
    "voice_profile_digest",
    "identity_history",
    "build_freshness",
}


def canonical_manifest_bytes(manifest: Mapping[str, object]) -> bytes:
    """Return the versioned canonical JSON encoding for a manifest value."""
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be a mapping")
    try:
        return json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError(f"manifest is not canonical JSON: {error}") from error


def payload_digest(payload: bytes) -> str:
    """Return the canonical SHA-256 digest label for a snapshot payload."""
    if not isinstance(payload, bytes):
        raise ValueError("payload must be bytes")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def release_id_for(manifest: Mapping[str, object]) -> str:
    """Address a manifest without including its self-referential release ID."""
    _validate_manifest(manifest)
    addressed_manifest = dict(manifest)
    del addressed_manifest["release_id"]
    return f"sha256:{hashlib.sha256(canonical_manifest_bytes(addressed_manifest)).hexdigest()}"


def verify_release(release_id: str, manifest: Mapping[str, object], payload: bytes) -> None:
    """Fail closed unless the pinned release, manifest, and payload agree."""
    _validate_manifest(manifest)
    if not isinstance(release_id, str) or not _RELEASE_ID.fullmatch(release_id):
        raise ValueError("release ID is not canonical sha256:<lowercase-hex>")
    calculated_release_id = release_id_for(manifest)
    if release_id != calculated_release_id:
        raise ValueError("release ID does not match manifest")
    if manifest["release_id"] != calculated_release_id:
        raise ValueError("manifest release_id does not match manifest")
    if manifest["payload_digest"] != payload_digest(payload):
        raise ValueError("payload digest does not match manifest")


def _validate_manifest(manifest: Mapping[str, object]) -> None:
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be a mapping")
    _require_fields(
        manifest,
        {
            "schema_version",
            "canonicalization_version",
            "hash_algorithm",
            "project_id",
            "project_id_scheme",
            "release_id",
            "payload_digest",
            "runtime",
            "provenance",
        },
        "manifest",
    )
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
    _require_fields(manifest["runtime"], _REQUIRED_RUNTIME_FIELDS, "runtime")
    _require_fields(manifest["provenance"], _REQUIRED_PROVENANCE_FIELDS, "provenance")
    canonical_manifest_bytes(manifest)


def _require_fields(value: object, fields: set[str], name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    missing = sorted(fields - value.keys())
    if missing:
        raise ValueError(f"{name} is missing required fields: {', '.join(missing)}")
