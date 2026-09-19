import hashlib
import json

from publication.manifest import canonical_manifest_bytes, canonical_payload_bytes, release_id_for
from vps.release_sync import ReleaseSync, SyncConfig, SyncError, read_pin, write_pin


class Store:
    def __init__(self, objects):
        self.objects = objects
        self.calls = []

    def get(self, key):
        self.calls.append(key)
        return self.objects.get(key)


def make_release(with_media=True):
    media = b"jpeg bytes"
    runtime = {
        "taxonomy": {"version": "1.0.0", "styles": [], "mechanics": [], "realism_values": []},
        "channels": [],
        "formulas": [],
        "cards": [{"frame_id": "frameA123"}],
        "mappings": [],
        "resolved_compilation_inputs": {"target_wpm": "215", "target_duration_s": ["1.5"], "shot_duration_s": ["2.5"]},
    }
    payload = canonical_payload_bytes({"runtime": runtime})
    manifest = {
        "schema_version": 1,
        "canonicalization_version": "json-c14n-v1",
        "hash_algorithm": "sha256",
        "project_id": "project",
        "project_id_scheme": "test",
        "release_id": "sha256:" + "0" * 64,
        "payload_digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "provenance": {
            "vault_commit": "a" * 40,
            "builder_version": "test",
            "taxonomy_module_digest": "sha256:" + "1" * 64,
            "module_digests": {},
            "sot_versions": {},
            "voice_profile_digest": "sha256:" + "2" * 64,
            "identity_history": [],
            "build_freshness": {"status": "fresh"},
        },
    }
    if with_media:
        manifest["media_digests"] = [{
            "media_id": "frameA123",
            "extension": ".jpg",
            "sha256": hashlib.sha256(media).hexdigest(),
            "size": len(media),
        }]
    manifest["release_id"] = release_id_for(manifest)
    return release_id_for(manifest), canonical_manifest_bytes(manifest), payload, media


def config(tmp_path):
    root = tmp_path / "state"
    return SyncConfig(
        pin_path=root / "pinned-release",
        state_path=root / "state.json",
        release_root=tmp_path / "releases",
        media_root=tmp_path / "media",
        endpoint="https://r2.example",
        bucket="private",
        prefix="releases/",
        region="auto",
        access_key="read",
        secret_key="secret",
    )


def objects(release, manifest, payload, media):
    digest = release[7:]
    return {
        f"releases/sha256/{digest}/manifest.json": manifest,
        f"releases/sha256/{digest}/payload.json": payload,
        "releases/media/frameA123.jpg": media,
    }


def test_sync_gets_exact_keys_and_materializes(tmp_path):
    release, manifest, payload, media = make_release()
    cfg = config(tmp_path)
    write_pin(cfg.pin_path, release, actor="operator", reason="test")
    store = Store(objects(release, manifest, payload, media))

    assert ReleaseSync(cfg, store).run()
    assert store.calls == [
        f"releases/sha256/{release[7:]}/manifest.json",
        f"releases/sha256/{release[7:]}/payload.json",
        "releases/media/frameA123.jpg",
    ]
    assert (cfg.release_root / "sha256" / release[7:] / "manifest.json").read_bytes() == manifest
    assert (cfg.release_root / "sha256" / release[7:] / "payload.json").read_bytes() == payload
    assert (cfg.media_root / "frameA123.jpg").read_bytes() == media
    state = json.loads(cfg.state_path.read_text())
    assert state["materialized_digest"] == release
    assert state["consecutive_failures"] == 0


def test_legacy_refused_and_active_untouched(tmp_path):
    release, manifest, payload, media = make_release(with_media=False)
    cfg = config(tmp_path)
    write_pin(cfg.pin_path, release, actor="operator", reason="test")
    active = cfg.release_root / "active.marker"
    active.parent.mkdir(parents=True)
    active.write_text("unchanged")

    assert not ReleaseSync(cfg, Store(objects(release, manifest, payload, media))).run()
    assert active.read_text() == "unchanged"
    assert not (cfg.release_root / "sha256" / release[7:]).exists()
    assert "legacy release is not reconstructible" in json.loads(cfg.state_path.read_text())["last_error"]


def test_media_digest_mismatch_does_not_materialize(tmp_path):
    release, manifest, payload, media = make_release()
    cfg = config(tmp_path)
    write_pin(cfg.pin_path, release, actor="operator", reason="test")
    active = cfg.release_root / "active.marker"
    active.parent.mkdir(parents=True)
    active.write_text("unchanged")

    bad = Store(objects(release, manifest, payload, b"tampered"))
    assert not ReleaseSync(cfg, bad).run()
    assert active.read_text() == "unchanged"
    assert not (cfg.release_root / "sha256" / release[7:]).exists()
    assert not cfg.media_root.exists()


def test_two_failures_notify_and_success_recovers(tmp_path):
    release, manifest, payload, media = make_release()
    cfg = config(tmp_path)
    write_pin(cfg.pin_path, release, actor="operator", reason="test")
    events = []

    class Down:
        def get(self, key):
            raise SyncError("R2 down")

    sync = ReleaseSync(cfg, Down(), events.append)
    assert not sync.run()
    assert events == []
    assert not sync.run()
    assert [event["event"] for event in events] == ["sync_failure"]
    sync.store = Store(objects(release, manifest, payload, media))
    assert sync.run()
    assert [event["event"] for event in events] == ["sync_failure", "sync_recovered"]


def test_pin_writer_audits_old_and_new(tmp_path):
    path = tmp_path / "pinned-release"
    first = "sha256:" + "1" * 64
    second = "sha256:" + "2" * 64
    write_pin(path, first, actor="alice", reason="first")
    write_pin(path, second, actor="bob", reason="second")
    assert read_pin(path) == second
    entries = [json.loads(line) for line in (tmp_path / "pinned-release.journal").read_text().splitlines()]
    assert entries[1]["old"] == first
    assert entries[1]["new"] == second
    assert entries[1]["actor"] == "bob"
