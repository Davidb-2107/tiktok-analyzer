"""Pure media-reference validation shared by publication adapters."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping


MEDIA_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
_ARTIFACT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MEDIA_FIELDS = {"media_id", "extension", "sha256", "size"}


def validate_artifact_id(media_id: object) -> str:
    if not isinstance(media_id, str) or _ARTIFACT_ID.fullmatch(media_id) is None:
        raise ValueError("media_id must be an opaque artifact ID")
    return media_id


def validate_media_extension(extension: object) -> str:
    if not isinstance(extension, str) or extension not in MEDIA_EXTENSIONS:
        raise ValueError("media extension is not supported")
    return extension


def canonical_media_digests(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("media_digests must be an array")

    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, raw_record in enumerate(value):
        if not isinstance(raw_record, Mapping):
            raise ValueError(f"media_digests[{index}] must be an object")
        if set(raw_record) != _MEDIA_FIELDS:
            raise ValueError(f"media_digests[{index}] has unexpected or missing fields")
        media_id = validate_artifact_id(raw_record["media_id"])
        if media_id in seen:
            raise ValueError(f"duplicate media_id: {media_id}")
        seen.add(media_id)
        extension = validate_media_extension(raw_record["extension"])
        digest = raw_record["sha256"]
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ValueError(f"media_digests[{index}].sha256 must be lowercase sha256 hex")
        size = raw_record["size"]
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise ValueError(f"media_digests[{index}].size must be a positive integer")
        records.append({"media_id": media_id, "extension": extension, "sha256": digest, "size": size})

    return sorted(records, key=lambda record: str(record["media_id"]))


def validate_media_digests_against_runtime(
    value: object,
    runtime: Mapping[str, object],
) -> None:
    canonical = canonical_media_digests(value)
    if value != canonical:
        raise ValueError("media_digests must be sorted canonically")

    cards = runtime.get("cards")
    if not isinstance(cards, list):
        raise ValueError("runtime.cards must be an array")
    referenced: set[str] = set()
    for index, card in enumerate(cards):
        if not isinstance(card, Mapping) or card.get("frame_id") is None:
            continue
        try:
            referenced.add(validate_artifact_id(card["frame_id"]))
        except ValueError as error:
            raise ValueError(f"media reference in runtime.cards[{index}] is invalid") from error

    declared = {str(record["media_id"]) for record in canonical}
    if declared != referenced:
        missing = sorted(referenced - declared)
        extra = sorted(declared - referenced)
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"extra {', '.join(extra)}")
        raise ValueError("media reference set does not match media_digests (" + "; ".join(details) + ")")


def require_media_digests(manifest: Mapping[str, object]) -> list[dict[str, object]]:
    value = manifest.get("media_digests")
    if value is None:
        raise ValueError("legacy release is not reconstructible: media_digests is absent")
    canonical = canonical_media_digests(value)
    if value != canonical:
        raise ValueError("media_digests must be sorted canonically")
    return canonical


def verify_media_bytes(record: Mapping[str, object], data: bytes | None) -> None:
    if data is None:
        raise ValueError(f"media is missing: {record.get('media_id')}")
    if len(data) != record["size"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError(f"media digest mismatch: {record.get('media_id')}")


def media_object_key(media_id: object, extension: object, *, prefix: str = "releases/media") -> str:
    media_id = validate_artifact_id(media_id)
    extension = validate_media_extension(extension)
    if not isinstance(prefix, str) or not prefix or prefix.startswith("/") or prefix.endswith("/"):
        raise ValueError("media object prefix must be a relative non-empty key prefix")
    if any(part in {"", ".", ".."} for part in prefix.split("/")):
        raise ValueError("media object prefix must contain normal path segments")
    return f"{prefix}/{media_id}{extension}"


__all__ = [
    "MEDIA_EXTENSIONS",
    "canonical_media_digests",
    "media_object_key",
    "require_media_digests",
    "validate_artifact_id",
    "validate_media_digests_against_runtime",
    "validate_media_extension",
    "verify_media_bytes",
]
