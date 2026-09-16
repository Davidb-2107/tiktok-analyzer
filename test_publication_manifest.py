import copy
import hashlib
import unittest

from publication.manifest import (
    canonical_manifest_bytes,
    payload_digest,
    release_id_for,
    verify_release,
)


def manifest_for(payload: bytes = b'{"cards":[]}') -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema_version": 1,
        "canonicalization_version": "json-c14n-v1",
        "hash_algorithm": "sha256",
        "project_id": "niche-42",
        "project_id_scheme": "niche-id-v1",
        "release_id": "sha256:" + "0" * 64,
        "payload_digest": payload_digest(payload),
        "runtime": {
            "taxonomy": {"version": "1.0.0", "styles": [], "mechanics": [], "realism_values": []},
            "channels": [],
            "formulas": [],
            "cards": [],
            "mappings": [],
            "resolved_compilation_inputs": {},
        },
        "provenance": {
            "vault_commit": "a" * 40,
            "builder_version": "builder-v1",
            "taxonomy_module_digest": "sha256:" + "b" * 64,
            "module_digests": {},
            "voice_profile_digest": "sha256:" + "c" * 64,
            "identity_history": [],
            "build_freshness": {"status": "fresh"},
        },
    }
    manifest["release_id"] = release_id_for(manifest)
    return manifest


class PublicationManifestTests(unittest.TestCase):
    def test_canonical_bytes_are_deterministic_and_preserve_unicode(self) -> None:
        # Break caught: changing JSON encoding, ordering, or Unicode escaping changes release identity.
        first = {"z": "é", "a": [1, 2]}
        second = {"a": [1, 2], "z": "é"}

        expected = b'{"a":[1,2],"z":"\xc3\xa9"}'

        self.assertEqual(canonical_manifest_bytes(first), expected)
        self.assertEqual(canonical_manifest_bytes(second), expected)

    def test_release_identity_excludes_its_embedded_value(self) -> None:
        # Break caught: hashing release_id itself makes a release impossible to verify non-circularly.
        manifest = manifest_for()
        expected = "sha256:" + hashlib.sha256(
            b'{"canonicalization_version":"json-c14n-v1","hash_algorithm":"sha256","payload_digest":"sha256:'
            + b"d" * 64
            + b'","project_id":"niche-42","project_id_scheme":"niche-id-v1","provenance":{"build_freshness":{"status":"fresh"},"builder_version":"builder-v1","identity_history":[],"module_digests":{},"taxonomy_module_digest":"sha256:'
            + b"b" * 64
            + b'","vault_commit":"'
            + b"a" * 40
            + b'","voice_profile_digest":"sha256:'
            + b"c" * 64
            + b'"},"runtime":{"cards":[],"channels":[],"formulas":[],"mappings":[],"resolved_compilation_inputs":{},"taxonomy":{"mechanics":[],"realism_values":[],"styles":[],"version":"1.0.0"}},"schema_version":1}'
        ).hexdigest()
        manifest["payload_digest"] = "sha256:" + "d" * 64
        manifest["release_id"] = "sha256:" + "0" * 64

        self.assertEqual(release_id_for(manifest), expected)

    def test_verify_release_accepts_a_pinned_matching_manifest_and_payload(self) -> None:
        # Break caught: a verifier that compares against embedded release_id or skips payload integrity.
        payload = b'{"cards":[]}'
        manifest = manifest_for(payload)

        self.assertIsNone(verify_release(manifest["release_id"], manifest, payload))

    def test_verify_release_rejects_manifest_payload_and_release_id_mutations(self) -> None:
        # Break caught: accepting a mutated pinned release, manifest, or payload.
        payload = b'{"cards":[]}'
        manifest = manifest_for(payload)

        mutated_manifest = copy.deepcopy(manifest)
        mutated_manifest["project_id"] = "other"
        with self.assertRaises(ValueError):
            verify_release(manifest["release_id"], mutated_manifest, payload)
        with self.assertRaises(ValueError):
            verify_release(manifest["release_id"], manifest, b'{"cards":[1]}')
        with self.assertRaises(ValueError):
            verify_release("SHA256:" + manifest["release_id"][7:].upper(), manifest, payload)

    def test_rejects_nan_and_unsupported_schema_or_hash_versions(self) -> None:
        # Break caught: accepting non-JSON values or silently reinterpreting an unsupported contract version.
        with self.assertRaises(ValueError):
            canonical_manifest_bytes({"value": float("nan")})

        manifest = manifest_for()
        manifest["schema_version"] = 2
        with self.assertRaises(ValueError):
            release_id_for(manifest)
        manifest = manifest_for()
        manifest["hash_algorithm"] = "sha512"
        with self.assertRaises(ValueError):
            release_id_for(manifest)


if __name__ == "__main__":
    unittest.main()
