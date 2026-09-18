import copy

import pytest

from publication.manifest import (
    canonical_manifest_bytes,
    canonical_payload_bytes,
    payload_digest,
    release_id_for,
    verify_release,
)
from publication.media import (
    canonical_media_digests,
    media_object_key,
    require_media_digests,
    verify_media_bytes,
)


def _runtime() -> dict[str, object]:
    return {
        "taxonomy": {"version": "1.0.0", "styles": [], "mechanics": [], "realism_values": []},
        "channels": [],
        "formulas": [],
        "cards": [{"frame_id": "frameA123"}],
        "mappings": [],
        "resolved_compilation_inputs": {
            "target_wpm": "215",
            "target_duration_s": ["1.5"],
            "shot_duration_s": ["2.5"],
        },
    }


def _manifest() -> tuple[dict[str, object], bytes]:
    media_digests = [{"media_id": "frameA123", "extension": ".jpg", "sha256": "a" * 64, "size": 4}]
    payload = canonical_payload_bytes({"runtime": _runtime()})
    manifest: dict[str, object] = {
        "schema_version": 1,
        "canonicalization_version": "json-c14n-v1",
        "hash_algorithm": "sha256",
        "project_id": "niche-42",
        "project_id_scheme": "niche-id-v1",
        "release_id": "sha256:" + "0" * 64,
        "payload_digest": payload_digest(payload),
        "provenance": {
            "vault_commit": "a" * 40,
            "builder_version": "builder-v1",
            "taxonomy_module_digest": "sha256:" + "b" * 64,
            "module_digests": {},
            "sot_versions": {},
            "voice_profile_digest": "sha256:" + "c" * 64,
            "identity_history": [],
            "build_freshness": {"status": "fresh"},
        },
        "media_digests": media_digests,
    }
    manifest["release_id"] = release_id_for(manifest)
    return manifest, payload


def test_media_helper_derives_stable_keys_and_canonical_order():
    records = [
        {"media_id": "b", "extension": ".png", "sha256": "b" * 64, "size": 2},
        {"media_id": "a", "extension": ".jpg", "sha256": "a" * 64, "size": 1},
    ]
    assert canonical_media_digests(records) == [records[1], records[0]]
    assert media_object_key("frameA123", ".jpg", prefix="releases/media") == "releases/media/frameA123.jpg"


def test_media_helper_rejects_malformed_duplicate_and_ambiguous_records():
    valid = {"media_id": "a", "extension": ".jpg", "sha256": "a" * 64, "size": 1}
    for invalid in (
        {**valid, "extension": ".gif"},
        {**valid, "sha256": "A" * 64},
        {**valid, "size": 0},
        {**valid, "unexpected": True},
        [valid, copy.deepcopy(valid)],
    ):
        with pytest.raises(ValueError):
            canonical_media_digests(invalid)


def test_manifest_accepts_optional_media_digests_and_matches_payload_cards():
    manifest, payload = _manifest()
    canonical_manifest_bytes(manifest)
    verify_release(manifest["release_id"], manifest, payload)

    mismatched = copy.deepcopy(manifest)
    mismatched["media_digests"][0]["media_id"] = "other"
    mismatched["release_id"] = release_id_for(mismatched)
    with pytest.raises(ValueError, match="media reference|media_digests"):
        verify_release(mismatched["release_id"], mismatched, payload)


def test_manifest_rejects_unsorted_or_extra_media_records():
    manifest, payload = _manifest()
    extra = {"media_id": "z", "extension": ".jpg", "sha256": "c" * 64, "size": 1}
    manifest["media_digests"] = [manifest["media_digests"][0], extra]
    manifest["release_id"] = release_id_for(manifest)
    with pytest.raises(ValueError, match="media reference|media_digests"):
        verify_release(manifest["release_id"], manifest, payload)

    missing = copy.deepcopy(manifest)
    missing["media_digests"] = []
    missing["release_id"] = release_id_for(missing)
    with pytest.raises(ValueError, match="media reference|media_digests"):
        verify_release(missing["release_id"], missing, payload)


def test_legacy_and_media_failures_have_distinct_messages():
    with pytest.raises(ValueError, match="legacy.*not reconstructible"):
        require_media_digests({})
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_media_bytes(
            {"media_id": "a", "extension": ".jpg", "sha256": "a" * 64, "size": 1},
            b"wrong",
        )
    with pytest.raises(ValueError, match="media is missing"):
        verify_media_bytes(
            {"media_id": "a", "extension": ".jpg", "sha256": "a" * 64, "size": 1},
            None,
        )
