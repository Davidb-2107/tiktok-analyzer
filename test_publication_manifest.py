import copy
import hashlib
import json
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from publication.manifest import (
    canonical_decimal_string,
    canonical_json_bytes,
    canonical_manifest_bytes,
    canonical_payload_bytes,
    parse_manifest_bytes,
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
            "resolved_compilation_inputs": {
                "target_wpm": "215",
                "target_duration_s": ["1.5", "0"],
                "shot_duration_s": ["2.5"],
            },
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
                canonical_json_bytes(vector["value"]),
                vector["expected_utf8"].encode("utf-8"),
                vector["name"],
            )

    def test_json_c14n_v1_rejects_floats_and_non_ascii_keys(self) -> None:
        # Break caught: accepting JSON numbers outside the integer-only contract.
        for value in (1.0, float("nan"), float("inf"), -0.0):
            with self.assertRaises(ValueError):
                canonical_json_bytes({"value": value})
        with self.assertRaises(ValueError):
            canonical_json_bytes({"é": 1})

    def test_json_c14n_v1_accepts_canonical_decimal_strings(self) -> None:
        # Break caught: converting fractional domain values through binary floats.
        self.assertEqual(canonical_json_bytes({"ratio": "1.25"}), b'{"ratio":"1.25"}')

    def test_decimal_v1_normalizes_exact_sources_and_rejects_float_or_bad_grammar(self) -> None:
        # Break caught: publishing binary-float artifacts or non-canonical decimal text.
        self.assertEqual(canonical_decimal_string(Decimal("215.0")), "215")
        self.assertEqual(canonical_decimal_string(Decimal("215")), "215")
        self.assertEqual(canonical_decimal_string("215.00"), "215")
        self.assertEqual(canonical_decimal_string(215), "215")
        self.assertEqual(canonical_decimal_string(Decimal("1.5")), "1.5")
        self.assertEqual(canonical_decimal_string(Decimal("-0.00")), "0")
        for value in (215.0, 1.5, "1e3", "01.5", "1.", Decimal("NaN"), Decimal("Infinity")):
            with self.assertRaises(ValueError):
                canonical_decimal_string(value)

    def test_canonical_manifest_bytes_requires_a_complete_manifest(self) -> None:
        # Break caught: using the generic serializer where a validated manifest is required.
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            canonical_manifest_bytes({"schema_version": 1})

    def test_payload_is_runtime_only_and_manifest_has_no_runtime_duplicate(self) -> None:
        # Break caught: reintroducing runtime into manifest.json or unrelated payload top-level data.
        manifest, _ = manifest_for()
        self.assertNotIn("runtime", manifest)
        with self.assertRaises(ValueError):
            release_id_for({**manifest, "runtime": runtime_payload()["runtime"]})
        with self.assertRaises(ValueError):
            canonical_payload_bytes({"runtime": {}, "provenance": {}})

    def test_payload_requires_all_runtime_schema_fields(self) -> None:
        # Break caught: accepting a payload that the checked-in schema rejects.
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            canonical_payload_bytes({"runtime": {"resolved_compilation_inputs": {}}})

    def test_declared_decimal_payload_paths_reject_noncanonical_values(self) -> None:
        # Break caught: silently rewriting alternate decimal spellings at the payload boundary.
        invalid_values = (
            ("target_wpm", "215.0"),
            ("target_wpm", 215.0),
            ("target_duration_s", ["1.5", "215.00"]),
            ("target_duration_s", ["1e0"]),
            ("shot_duration_s", ["-0"]),
            ("shot_duration_s", [1.5]),
        )
        for field, value in invalid_values:
            payload = runtime_payload()
            payload["runtime"]["resolved_compilation_inputs"][field] = value
            with self.assertRaisesRegex(ValueError, "decimal-v1"):
                canonical_payload_bytes(payload)

    def test_manifest_bytes_are_strictly_parsed_before_release_verification(self) -> None:
        # Break caught: silently normalizing stored manifest bytes before hashing release identity.
        manifest, payload = manifest_for()
        stored = canonical_manifest_bytes(manifest)
        self.assertEqual(parse_manifest_bytes(stored), manifest)

        with patch("publication.manifest._read_canonical_json", return_value={}):
            with self.assertRaisesRegex(ValueError, "missing required fields"):
                parse_manifest_bytes(b"{}")

        duplicate = stored[:-1] + b',"project_id":"niche-42"}'
        noncanonical = stored.replace(b"{", b"{ ", 1)
        for invalid in (duplicate, noncanonical):
            with self.assertRaisesRegex(ValueError, "canonical|duplicate"):
                parse_manifest_bytes(invalid)
            with self.assertRaisesRegex(ValueError, "canonical|duplicate"):
                verify_release(manifest["release_id"], invalid, payload)

    def test_canonical_but_incomplete_manifest_bytes_are_rejected(self) -> None:
        # Break caught: returning canonical JSON without enforcing the manifest schema.
        incomplete = canonical_json_bytes({"schema_version": 1})
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            parse_manifest_bytes(incomplete)

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
        expected = "sha256:a210d37dbce40fc80303ed37a98a2280e577cf9f0340c0bde8a476ed9e192223"
        self.assertEqual(release_id_for({**manifest, "release_id": "sha256:" + "f" * 64}), expected)
        with patch("publication.manifest.canonical_manifest_bytes", side_effect=AssertionError):
            self.assertEqual(release_id_for(manifest), expected)
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
