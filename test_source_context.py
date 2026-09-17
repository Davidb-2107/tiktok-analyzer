"""Source-context contract tests.  Run: python test_source_context.py."""

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from publication.manifest import (
    canonical_json_bytes,
    canonical_payload_bytes,
    payload_digest,
    release_id_for,
)
from publication.source import parse_source_context, resolve_source
import brief_compiler as bc


def _payload():
    return {
        "runtime": {
            "taxonomy": {"version": "1.0.0", "styles": [], "mechanics": [], "realism_values": []},
            "channels": [],
            "formulas": [],
            "cards": [],
            "mappings": [],
            "wpm_source": "measured corpus: exact provenance",
            "resolved_compilation_inputs": {
                "target_wpm": "215",
                "target_duration_s": ["62"],
                "shot_duration_s": ["2.5"],
            },
        }
    }


def _write_snapshot(directory, payload=None, validate_payload=True, project_id="niche-42"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    payload = payload or _payload()
    payload_bytes = canonical_payload_bytes(payload) if validate_payload else canonical_json_bytes(payload)
    manifest = {
        "schema_version": 1,
        "canonicalization_version": "json-c14n-v1",
        "hash_algorithm": "sha256",
        "project_id": project_id,
        "project_id_scheme": "niche-id-v1",
        "release_id": "sha256:" + "0" * 64,
        # Intentionally malformed payload fixtures cannot pass through the
        # validating payload_digest helper; the source adapter must reject them
        # when it reads the stored bytes.
        "payload_digest": (
            payload_digest(payload_bytes)
            if validate_payload
            else "sha256:" + hashlib.sha256(payload_bytes).hexdigest()
        ),
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
    (directory / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    (directory / "payload.json").write_bytes(payload_bytes)
    return manifest, payload_bytes


class SourceContextTests(unittest.TestCase):
    def test_compiler_requires_an_explicit_source_context(self):
        with self.assertRaisesRegex(ValueError, "source context"):
            bc.compile_brief("source_fixture")

    def test_parse_source_context_requires_an_explicit_known_context(self):
        # Break caught: accepting an implicit Vault path or an unknown adapter.
        parsed = parse_source_context("local:C:/drafts/neon")
        self.assertEqual(parsed.kind, "local")
        self.assertEqual(parsed.value, "C:/drafts/neon")
        self.assertEqual(
            parse_source_context("release:sha256:" + "a" * 64).value,
            "sha256:" + "a" * 64,
        )
        for context in (None, "", "draft", "local:", "local:   ", "remote:x", "release:not-an-id"):
            with self.subTest(context=context):
                with self.assertRaisesRegex(ValueError, "source context"):
                    parse_source_context(context)

    def test_local_and_release_read_the_same_canonical_payload_bytes(self):
        # Break caught: adapters parsing/reserializing differently or release lookup using another snapshot.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, payload_bytes = _write_snapshot(root / "draft")
            release_dir = root / "releases" / "sha256" / manifest["release_id"].split(":", 1)[1]
            _write_snapshot(release_dir)
            local = resolve_source(parse_source_context(f"local:{root / 'draft'}"))
            release = resolve_source(
                parse_source_context(f"release:{manifest['release_id']}"),
                release_root=root / "releases",
            )
            self.assertEqual(local.payload_bytes, payload_bytes)
            self.assertEqual(release.payload_bytes, payload_bytes)
            self.assertEqual(local.payload_bytes, release.payload_bytes)
            self.assertEqual(local.runtime["wpm_source"], "measured corpus: exact provenance")
            self.assertNotIn(str(root), local.runtime)
            self.assertEqual(local.runtime["resolved_compilation_inputs"]["target_wpm"], 215.0)
            self.assertEqual(
                local.runtime["resolved_compilation_inputs"]["target_duration_s"],
                [62.0],
            )

    def test_context_and_canonical_storage_fail_closed(self):
        # Break caught: accepting implicit contexts, malformed paths, or noncanonical stored bytes.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, _ = _write_snapshot(root / "draft")
            for context in (None, "", "draft", "local:", "release:not-an-id"):
                with self.subTest(context=context):
                    with self.assertRaises(ValueError):
                        resolve_source(parse_source_context(context))
            with self.assertRaisesRegex(ValueError, "release_root"):
                resolve_source(parse_source_context(f"release:{manifest['release_id']}"))
            (root / "draft" / "payload.json").write_bytes(b'{ "runtime": {}}')
            with self.assertRaisesRegex(ValueError, "canonical"):
                resolve_source(parse_source_context(f"local:{root / 'draft'}"))

    def test_missing_measurements_and_transcript_verbatim_fail_closed(self):
        # Break caught: compiler receiving an incomplete measurement set or transcript-bearing runtime payload.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            incomplete = _payload()
            del incomplete["runtime"]["resolved_compilation_inputs"]["target_wpm"]
            _write_snapshot(root / "incomplete", incomplete, validate_payload=False)
            with self.assertRaisesRegex(ValueError, "missing required fields"):
                resolve_source(parse_source_context(f"local:{root / 'incomplete'}"))
            poison = _payload()
            poison["runtime"]["transcript"] = "DO NOT COPY THIS VERBATIM"
            _write_snapshot(root / "poison", poison)
            with self.assertRaisesRegex(ValueError, "transcript"):
                resolve_source(parse_source_context(f"local:{root / 'poison'}"))

    def test_duplicate_manifest_and_payload_bytes_fail_closed(self):
        # Break caught: parsing/re-serializing noncanonical stored JSON.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, payload_bytes = _write_snapshot(root / "draft")
            manifest_path = root / "draft" / "manifest.json"
            manifest_bytes = manifest_path.read_bytes()
            manifest_path.write_bytes(b" " + manifest_bytes)
            with self.assertRaisesRegex(ValueError, "canonical"):
                resolve_source(parse_source_context(f"local:{root / 'draft'}"))

            manifest_path.write_bytes(b'{"project_id":"niche-42",' + manifest_bytes[1:])
            with self.assertRaisesRegex(ValueError, "duplicate"):
                resolve_source(parse_source_context(f"local:{root / 'draft'}"))

            _write_snapshot(root / "draft", validate_payload=True)
            (root / "draft" / "payload.json").write_bytes(
                payload_bytes[:-1] + b',"runtime":{}}'
            )
            with self.assertRaisesRegex(ValueError, "canonical|duplicate"):
                resolve_source(parse_source_context(f"local:{root / 'draft'}"))


if __name__ == "__main__":
    unittest.main()
