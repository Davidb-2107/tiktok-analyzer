import copy
import hashlib
import json
import unittest
from pathlib import Path

from publication.manifest import (
    canonical_manifest_bytes,
    canonical_payload_bytes,
    payload_digest,
    release_id_for,
    verify_release,
)


VECTORS = json.loads(
    (Path(__file__).parent / "publication" / "canonicalization-v1-vectors.json").read_text(encoding="utf-8")
)


def runtime_payload() -> dict[str, object]:
    return {
        "runtime": {
            "taxonomy": {"version": "1.0.0", "styles": [], "mechanics": [], "realism_values": []},
            "channels": [],
            "formulas": [],
            "cards": [],
            "mappings": [],
            "resolved_compilation_inputs": {},
        }
    }


def manifest_for(payload: bytes | None = None) -> tuple[dict[str, object], bytes]:
    if payload is None:
        payload = canonical_payload_bytes(runtime_payload())
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
    }
    manifest["release_id"] = release_id_for(manifest)
    return manifest, payload


class PublicationManifestTests(unittest.TestCase):
    def test_known_answer_vectors_define_json_c14n_v1_bytes(self) -> None:
        # Break caught: changing key order, NFC normalization, or compact UTF-8 output.
        for vector in VECTORS["mapping_vectors"]:
            self.assertEqual(
                canonical_manifest_bytes(vector["value"]),
                vector["expected_utf8"].encode("utf-8"),
                vector["name"],
            )

    def test_json_c14n_v1_rejects_floats_and_non_ascii_keys(self) -> None:
        # Break caught: accepting JSON numbers outside the integer-only contract.
        for value in (1.0, float("nan"), float("inf"), -0.0):
            with self.assertRaises(ValueError):
                canonical_manifest_bytes({"value": value})
        with self.assertRaises(ValueError):
            canonical_manifest_bytes({"é": 1})

    def test_json_c14n_v1_accepts_canonical_decimal_strings(self) -> None:
        # Break caught: converting fractional domain values through binary floats.
        self.assertEqual(canonical_manifest_bytes({"ratio": "1.25"}), b'{"ratio":"1.25"}')

    def test_payload_is_runtime_only_and_manifest_has_no_runtime_duplicate(self) -> None:
        # Break caught: reintroducing runtime into manifest.json or unrelated payload top-level data.
        manifest, _ = manifest_for()
        self.assertNotIn("runtime", manifest)
        with self.assertRaises(ValueError):
            release_id_for({**manifest, "runtime": runtime_payload()["runtime"]})
        with self.assertRaises(ValueError):
            canonical_payload_bytes({"runtime": {}, "provenance": {}})

    def test_duplicate_and_noncanonical_stored_payload_bytes_are_rejected(self) -> None:
        # Break caught: silently parsing and reserializing stored payload bytes.
        manifest, payload = manifest_for()
        for stored in (
            b'{ "runtime": {"resolved_compilation_inputs": {}, "cards": [], "channels": [], "formulas": [], "mappings": [], "taxonomy": {"mechanics": [], "realism_values": [], "styles": [], "version": "1.0.0"}}}',
            b'{"runtime":{"resolved_compilation_inputs":{},"cards":[],"channels":[],"formulas":[],"mappings":[],"taxonomy":{"mechanics":[],"realism_values":[],"styles":[],"version":"1.0.0"},"x":1,"x":2}}',
            b'{"runtime":{"resolved_compilation_inputs":{},"label":"e\xcc\x81"}}',
        ):
            with self.assertRaisesRegex(ValueError, "canonical|duplicate"):
                verify_release(manifest["release_id"], manifest, stored)
        verify_release(manifest["release_id"], manifest, payload)

    def test_stored_number_vectors_are_rejected_before_payload_hashing(self) -> None:
        # Break caught: accepting a float or negative zero after JSON parsing loses its original spelling.
        manifest, _ = manifest_for()
        for vector in VECTORS["rejected_stored_bytes"]:
            if vector["name"] == "duplicate-key":
                stored = b'{"runtime":' + vector["utf8"].encode("utf-8") + b'}'
            else:
                number = vector["utf8"].split(":", 1)[1][:-1]
                stored = b'{"runtime":{"resolved_compilation_inputs":{},"value":' + number.encode("ascii") + b'}}'
            with self.assertRaisesRegex(ValueError, "canonical|duplicate|number"):
                verify_release(manifest["release_id"], manifest, stored)

    def test_payload_digest_is_the_exact_canonical_payload_bytes_digest(self) -> None:
        # Break caught: hashing a reserialized or manifest-embedded runtime instead of payload.json bytes.
        _, payload = manifest_for()
        expected = "sha256:" + hashlib.sha256(payload).hexdigest()
        self.assertEqual(payload_digest(payload), expected)
        with self.assertRaises(ValueError):
            payload_digest(payload + b"\n")

    def test_release_identity_is_non_circular_and_verification_is_strict(self) -> None:
        # Break caught: trusting embedded release_id or accepting manifest/payload mutations.
        manifest, payload = manifest_for()
        expected = "sha256:64e814d5ea1f351336cd4234f38019fcf343f77b227ccb4bfe9da68d6f67aa50"
        self.assertEqual(release_id_for({**manifest, "release_id": "sha256:" + "f" * 64}), expected)
        verify_release(manifest["release_id"], manifest, payload)

        mutated_manifest = copy.deepcopy(manifest)
        mutated_manifest["project_id"] = "other"
        with self.assertRaises(ValueError):
            verify_release(manifest["release_id"], mutated_manifest, payload)
        with self.assertRaises(ValueError):
            verify_release(manifest["release_id"], manifest, payload[:-1] + b"0")
        with self.assertRaises(ValueError):
            verify_release("SHA256:" + manifest["release_id"][7:].upper(), manifest, payload)

    def test_manifest_rejects_unsupported_versions_and_provenance_renames(self) -> None:
        # Break caught: silently accepting a new canonicalization/schema contract or old provenance spelling.
        manifest, _ = manifest_for()
        for field, value in (("schema_version", 2), ("canonicalization_version", "json-c14n-v2"), ("hash_algorithm", "sha512")):
            changed = copy.deepcopy(manifest)
            changed[field] = value
            with self.assertRaises(ValueError):
                release_id_for(changed)
        changed = copy.deepcopy(manifest)
        del changed["provenance"]["sot_versions"]
        changed["provenance"]["sot_version"] = {}
        with self.assertRaises(ValueError):
            release_id_for(changed)


if __name__ == "__main__":
    unittest.main()
