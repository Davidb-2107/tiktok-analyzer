import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import brief_compiler as bc
from publication.identity import (
    allocate_channel_id,
    validate_channel_record,
    validate_identity_index,
    validate_runtime_payload,
)


def _history_entry(
    handle="@alpha",
    valid_from="2026-01-01T00:00:00Z",
    valid_to=None,
    evidence="vault://identity/alpha",
):
    return {
        "handle": handle,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "valid_from_precision": "exact",
        "valid_to_precision": "exact" if valid_to is not None else "approximate",
        "evidence": evidence,
        "declared_by": "actor-1",
        "declared_at": "2026-01-02T00:00:00Z",
    }


def _channel(
    channel_id="alpha",
    scheme="handle-slug-v1",
    current_handle="@alpha",
    history=None,
):
    return {
        "channel_id": channel_id,
        "channel_id_scheme": scheme,
        "current_handle": current_handle,
        "handle_history": history or [_history_entry(current_handle)],
    }


def _index(*records):
    return {"channels": list(records)}


def _runtime():
    return {
        "taxonomy": {
            "version": "1.0.0",
            "styles": ["AI animation"],
            "mechanics": ["question"],
            "realism_values": [1, 5],
        },
        "channels": [_channel()],
        "formulas": [],
        "cards": [],
        "mappings": [],
        "resolved_compilation_inputs": {
            "target_wpm": "215",
            "target_duration_s": ["62", "75"],
            "shot_duration_s": ["2.5"],
        },
    }


class ChannelIdentityTests(unittest.TestCase):
    def test_unused_existing_handle_uses_frozen_slug_scheme(self):
        self.assertEqual(
            allocate_channel_id("neon_psycho", "@alpha", _index()),
            ("alpha", "handle-slug-v1"),
        )
        self.assertEqual(
            allocate_channel_id("neon_psycho", "@beta", {}),
            ("beta", "handle-slug-v1"),
        )

    def test_collision_allocates_opaque_id_and_mixed_schemes_are_valid(self):
        existing = {
            "project_id": "neon_psycho",
            "channel_id": "alpha",
            "channel_id_scheme": "handle-slug-v1",
            "origin_handle": "@alpha",
            "origin_release": "release-1",
            "actor": "actor-1",
            "evidence": "vault://identity/alpha",
            "handle_history": [_history_entry()],
        }
        index = _index(existing)
        allocated, scheme = allocate_channel_id("neon_psycho", "@alpha", index)
        self.assertNotEqual(allocated, "alpha")
        self.assertEqual(scheme, "opaque-v1")
        self.assertIsInstance(allocated, str)

        opaque = dict(existing)
        opaque.update(
            {
                "channel_id": allocated,
                "channel_id_scheme": scheme,
                "origin_handle": "@beta",
                "origin_release": "release-2",
                "handle_history": [_history_entry("@beta")],
            }
        )
        validate_identity_index(_index(existing, opaque))

    def test_channel_record_requires_open_interval_projection(self):
        with self.assertRaisesRegex(ValueError, "current_handle"):
            validate_channel_record(
                _channel(
                    current_handle="@beta",
                    history=[_history_entry("@alpha")],
                )
            )

        with self.assertRaisesRegex(ValueError, "open"):
            validate_channel_record(
                _channel(
                    history=[
                        _history_entry("@alpha", valid_to="2026-02-01T00:00:00Z"),
                    ]
                )
            )

    def test_overlapping_intervals_within_one_channel_are_rejected(self):
        history = [
            _history_entry("@alpha", valid_to="2026-03-01T00:00:00Z"),
            _history_entry(
                "@beta",
                valid_from="2026-02-01T00:00:00Z",
                valid_to=None,
            ),
        ]
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_channel_record(_channel(current_handle="@beta", history=history))

    def test_same_handle_overlapping_across_channel_ids_is_rejected(self):
        first = {
            "project_id": "neon_psycho",
            "channel_id": "alpha",
            "channel_id_scheme": "handle-slug-v1",
            "origin_handle": "@alpha",
            "origin_release": "release-1",
            "actor": "actor-1",
            "evidence": "evidence-1",
            "handle_history": [_history_entry("@alpha")],
        }
        second = dict(first)
        second.update(
            {
                "channel_id": "opaque-1",
                "channel_id_scheme": "opaque-v1",
                "origin_release": "release-2",
            }
        )
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_identity_index(_index(first, second))

    def test_touching_intervals_are_not_overlapping(self):
        history = [
            _history_entry("@alpha", valid_to="2026-02-01T00:00:00Z"),
            _history_entry(
                "@beta",
                valid_from="2026-02-01T00:00:00Z",
                valid_to=None,
            ),
        ]
        validate_channel_record(_channel(current_handle="@beta", history=history))

    def test_runtime_required_fields_are_loaded_from_checked_in_schema(self):
        schema = json.loads(
            Path(__file__).with_name("publication")
            .joinpath("snapshot.schema.json")
            .read_text(encoding="utf-8")
        )
        required = schema["$defs"]["runtime"]["required"]
        for field in required:
            runtime = _runtime()
            del runtime[field]
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "missing required fields"):
                    validate_runtime_payload(runtime, project_id="neon_psycho")

    def test_malformed_taxonomy_and_channel_records_are_rejected(self):
        runtime = _runtime()
        del runtime["taxonomy"]["styles"]
        with self.assertRaisesRegex(ValueError, "taxonomy"):
            validate_runtime_payload(runtime, project_id="neon_psycho")

        runtime = _runtime()
        runtime["channels"][0]["channel_id_scheme"] = "project-wide-v1"
        with self.assertRaisesRegex(ValueError, "channel_id_scheme"):
            validate_runtime_payload(runtime, project_id="neon_psycho")

    def test_resolved_measurements_are_required_nonempty_canonical_strings(self):
        for field in ("target_wpm", "target_duration_s", "shot_duration_s"):
            runtime = _runtime()
            del runtime["resolved_compilation_inputs"][field]
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "resolved_compilation_inputs"):
                    validate_runtime_payload(runtime, project_id="neon_psycho")

        for field in ("target_duration_s", "shot_duration_s"):
            runtime = _runtime()
            runtime["resolved_compilation_inputs"][field] = []
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "non-empty"):
                    validate_runtime_payload(runtime, project_id="neon_psycho")

        invalid_values = {
            "target_wpm": "215.0",
            "target_duration_s": ["1e2"],
            "shot_duration_s": [1.5],
        }
        for field, value in invalid_values.items():
            runtime = _runtime()
            runtime["resolved_compilation_inputs"][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "decimal-v1"):
                    validate_runtime_payload(runtime, project_id="neon_psycho")

    def test_subformula_and_video_assignment_keys_are_channel_scoped(self):
        runtime = _runtime()
        runtime["formulas"] = [
            {
                "channel_id": "alpha",
                "subformula_id": "alpha_legacy_01",
            }
        ]
        runtime["mappings"] = [
            {
                "channel_id": "alpha",
                "subformula_id": "alpha_legacy_01",
                "video_id": "video-1",
            },
            {
                "channel_id": "alpha",
                "subformula_id": "alpha_legacy_01",
                "video_id": "video-2",
            },
        ]
        validate_runtime_payload(runtime, project_id="neon_psycho")

        duplicate = dict(runtime)
        duplicate["mappings"] = runtime["mappings"] + [
            {
                "channel_id": "alpha",
                "subformula_id": "other_legacy_02",
                "video_id": "video-1",
            }
        ]
        with self.assertRaisesRegex(ValueError, "video assignment"):
            validate_runtime_payload(duplicate, project_id="neon_psycho")

        duplicate_subformula = dict(runtime)
        duplicate_subformula["formulas"] = runtime["formulas"] + [
            {
                "channel_id": "alpha",
                "subformula_id": "alpha_legacy_01",
            }
        ]
        with self.assertRaisesRegex(ValueError, "subformula"):
            validate_runtime_payload(duplicate_subformula, project_id="neon_psycho")

    @contextmanager
    def _temporary_transcript(self, *, channel="@old_handle", channel_id="frozen-id"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcripts = root / "neon_psycho" / channel_id
            transcripts.mkdir(parents=True)
            card = transcripts / "1234567890123456789.md"
            card.write_text(
                "---\n"
                "video_url: https://www.tiktok.com/@old_handle/video/1234567890123456789\n"
                f'channel: "{channel}"\n'
                f"channel_id: {channel_id}\n"
                "---\n\n"
                "## Transcript\n\nSynthetic transcript.\n",
                encoding="utf-8",
            )
            old_transcripts = bc.TRANSCRIPTS
            old_inspect = bc.fcr.inspect_file
            bc.TRANSCRIPTS = root
            bc.fcr.inspect_file = lambda _: {
                "n_sections": 0,
                "valid": False,
                "errors": [],
                "card": None,
            }
            try:
                yield
            finally:
                bc.TRANSCRIPTS = old_transcripts
                bc.fcr.inspect_file = old_inspect

    def test_loader_accepts_old_handle_when_declared_id_matches_partition(self):
        with self._temporary_transcript():
            videos = bc.load_registry("neon_psycho", channel="@old_handle")
        self.assertEqual(videos[0]["channel"], "@old_handle")
        self.assertEqual(videos[0]["channel_id"], "frozen-id")

    def test_loader_rejects_missing_or_mismatched_declared_channel_id(self):
        with self._temporary_transcript(channel_id="frozen-id"):
            card = bc.TRANSCRIPTS / "neon_psycho" / "frozen-id" / "1234567890123456789.md"
            text = card.read_text(encoding="utf-8").replace("channel_id: frozen-id\n", "")
            card.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "channel_id"):
                bc.load_registry("neon_psycho", channel="@old_handle")

        with self._temporary_transcript(channel_id="frozen-id"):
            card = bc.TRANSCRIPTS / "neon_psycho" / "frozen-id" / "1234567890123456789.md"
            text = card.read_text(encoding="utf-8").replace(
                "channel_id: frozen-id\n", "channel_id: tampered-id\n"
            )
            card.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "partition"):
                bc.load_registry("neon_psycho", channel="@old_handle")


if __name__ == "__main__":
    unittest.main()
