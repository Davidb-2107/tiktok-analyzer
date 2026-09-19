import hashlib
import json

import pytest
import vps.activation as activation_module

from publication.manifest import canonical_manifest_bytes, canonical_payload_bytes, release_id_for
from vps.activation import (
    ActivationConfig,
    ActivationLegacyRelease,
    ActiveStateUnknown,
    DigestMismatch,
    IncompleteMaterialization,
    LocalGarbageCollector,
    MissingMedia,
    NotMaterialized,
    PinMismatch,
    ReleaseActivator,
)
from vps.release_sync import read_pin, write_pin


def test_external_verification_identifies_activation_client(monkeypatch):
    release_id = "sha256:" + "a" * 64
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps({"release_id": release_id}).encode("utf-8")

    def fake_urlopen(request, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(activation_module, "urlopen", fake_urlopen)
    activation_module.CommandHubController("unused", "https://example.test/hub").verify_external(release_id)

    assert seen["request"].get_header("User-agent") == "tiktok-analyzer-activation/1"
    assert seen["request"].get_header("Accept") == "application/json"


class Hub:
    def __init__(self):
        self.reloads = []
        self.verifications = []

    def reload(self, release_id):
        self.reloads.append(release_id)

    def verify_external(self, release_id):
        self.verifications.append(release_id)


def make_release(label="A", with_media=True):
    media_id = f"frame{label}123"
    media = f"media-{label}".encode()
    runtime = {
        "taxonomy": {"version": "1.0.0", "styles": [], "mechanics": [], "realism_values": []},
        "channels": [],
        "formulas": [],
        "cards": [{"frame_id": media_id}],
        "mappings": [],
        "resolved_compilation_inputs": {"target_wpm": "215", "target_duration_s": ["1.5"], "shot_duration_s": ["2.5"]},
    }
    payload = canonical_payload_bytes({"runtime": runtime})
    manifest = {
        "schema_version": 1,
        "canonicalization_version": "json-c14n-v1",
        "hash_algorithm": "sha256",
        "project_id": f"project-{label}",
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
            "media_id": media_id,
            "extension": ".jpg",
            "sha256": hashlib.sha256(media).hexdigest(),
            "size": len(media),
        }]
    manifest["release_id"] = release_id_for(manifest)
    return release_id_for(manifest), canonical_manifest_bytes(manifest), payload, media, media_id


def config(tmp_path):
    root = tmp_path / "state"
    return ActivationConfig(
        pin_path=root / "pinned-release",
        active_path=root / "active-release",
        previous_path=root / "previous-release",
        journal_path=root / "activation.journal",
        release_root=tmp_path / "releases",
        media_root=tmp_path / "media",
        reload_command=None,
        external_url=None,
    )


def materialize(cfg, release, manifest, payload, media, media_id):
    directory = cfg.release_root / "sha256" / release[7:]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_bytes(manifest)
    (directory / "payload.json").write_bytes(payload)
    cfg.media_root.mkdir(parents=True, exist_ok=True)
    (cfg.media_root / f"{media_id}.jpg").write_bytes(media)


def test_activation_revalidates_and_records_previous(tmp_path):
    cfg = config(tmp_path)
    release, manifest, payload, media, media_id = make_release()
    materialize(cfg, release, manifest, payload, media, media_id)
    write_pin(cfg.pin_path, release, actor="operator", reason="promote")
    cfg.active_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.active_path.write_text("sha256:" + "1" * 64)
    hub = Hub()

    assert ReleaseActivator(cfg, hub).activate(release, actor="operator", reason="promote") == release
    assert read_pin(cfg.pin_path) == release
    assert cfg.active_path.read_text().strip() == release
    assert cfg.previous_path.read_text().strip() == "sha256:" + "1" * 64
    assert hub.reloads == [release]
    assert hub.verifications == [release]
    journal = [json.loads(line) for line in cfg.journal_path.read_text().splitlines()]
    assert journal[-1]["new"] == release


def test_activation_is_idempotent_when_already_active(tmp_path):
    cfg = config(tmp_path)
    release, manifest, payload, media, media_id = make_release()
    materialize(cfg, release, manifest, payload, media, media_id)
    write_pin(cfg.pin_path, release, actor="operator", reason="promote")
    cfg.active_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.active_path.write_text(release)
    hub = Hub()

    ReleaseActivator(cfg, hub).activate(release, actor="operator", reason="repeat")
    assert hub.reloads == []
    assert hub.verifications == [release]


@pytest.mark.parametrize("error", [PinMismatch, NotMaterialized])
def test_activation_refuses_undeclared_or_missing_target(tmp_path, error):
    cfg = config(tmp_path)
    release, manifest, payload, media, media_id = make_release()
    other, *_ = make_release("B")
    if error is PinMismatch:
        write_pin(cfg.pin_path, other, actor="operator", reason="test")
        materialize(cfg, release, manifest, payload, media, media_id)
    else:
        write_pin(cfg.pin_path, release, actor="operator", reason="test")
    with pytest.raises(error):
        ReleaseActivator(cfg, Hub()).activate(release, actor="operator", reason="test")


def test_activation_refuses_legacy_incomplete_and_missing_media(tmp_path):
    cfg = config(tmp_path)
    legacy, manifest, payload, media, media_id = make_release("L", with_media=False)
    materialize(cfg, legacy, manifest, payload, media, media_id)
    write_pin(cfg.pin_path, legacy, actor="operator", reason="test")
    with pytest.raises(ActivationLegacyRelease):
        ReleaseActivator(cfg, Hub()).activate(legacy, actor="operator", reason="test")

    release, manifest, payload, media, media_id = make_release()
    materialize(cfg, release, manifest, payload, media, media_id)
    write_pin(cfg.pin_path, release, actor="operator", reason="test")
    (cfg.media_root / f"{media_id}.jpg").unlink()
    with pytest.raises(MissingMedia):
        ReleaseActivator(cfg, Hub()).activate(release, actor="operator", reason="test")

    directory = cfg.release_root / "sha256" / release[7:]
    (directory / "payload.json").unlink()
    with pytest.raises(IncompleteMaterialization):
        ReleaseActivator(cfg, Hub()).activate(release, actor="operator", reason="test")


def test_activation_refuses_tampered_media(tmp_path):
    cfg = config(tmp_path)
    release, manifest, payload, media, media_id = make_release()
    materialize(cfg, release, manifest, payload, media, media_id)
    write_pin(cfg.pin_path, release, actor="operator", reason="test")
    (cfg.media_root / f"{media_id}.jpg").write_bytes(b"tampered")

    with pytest.raises(DigestMismatch):
        ReleaseActivator(cfg, Hub()).activate(release, actor="operator", reason="test")


def test_rollback_updates_pin_then_uses_same_activation_primitive(tmp_path):
    cfg = config(tmp_path)
    active, active_manifest, active_payload, active_media, active_id = make_release("A")
    previous, previous_manifest, previous_payload, previous_media, previous_id = make_release("B")
    materialize(cfg, active, active_manifest, active_payload, active_media, active_id)
    materialize(cfg, previous, previous_manifest, previous_payload, previous_media, previous_id)
    cfg.active_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.active_path.write_text(active)
    cfg.previous_path.write_text(previous)
    write_pin(cfg.pin_path, active, actor="operator", reason="promote")
    hub = Hub()

    assert ReleaseActivator(cfg, hub).rollback(actor="operator", reason="restore previous") == previous
    assert read_pin(cfg.pin_path) == previous
    assert cfg.active_path.read_text().strip() == previous
    assert cfg.previous_path.read_text().strip() == active
    assert hub.reloads == [previous]
    assert hub.verifications == [previous]


def test_rollback_syncs_previous_when_local_copy_is_missing(tmp_path):
    cfg = config(tmp_path)
    active, active_manifest, active_payload, active_media, active_id = make_release("A")
    previous, previous_manifest, previous_payload, previous_media, previous_id = make_release("B")
    materialize(cfg, active, active_manifest, active_payload, active_media, active_id)
    cfg.active_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.active_path.write_text(active)
    cfg.previous_path.write_text(previous)
    write_pin(cfg.pin_path, active, actor="operator", reason="promote")
    prepared = []

    def sync_previous():
        prepared.append(previous)
        materialize(cfg, previous, previous_manifest, previous_payload, previous_media, previous_id)
        return True

    assert ReleaseActivator(cfg, Hub(), sync_previous).rollback(actor="operator", reason="restore previous") == previous
    assert prepared == [previous]


def test_gc_keeps_active_previous_pinned_and_referenced_media(tmp_path):
    cfg = config(tmp_path)
    releases = [make_release(label) for label in ("A", "B", "C", "D")]
    for item in releases:
        materialize(cfg, *item)
    cfg.active_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.active_path.write_text(releases[0][0])
    cfg.previous_path.write_text(releases[1][0])
    write_pin(cfg.pin_path, releases[2][0], actor="operator", reason="promote")
    orphan = cfg.media_root / "orphan.jpg"
    orphan.write_bytes(b"orphan")

    result = LocalGarbageCollector(cfg).collect()
    assert result["deleted_releases"] == 1
    assert not (cfg.release_root / "sha256" / releases[3][0][7:]).exists()
    assert not (cfg.media_root / f"{releases[3][4]}.jpg").exists()
    assert not orphan.exists()
    assert all((cfg.release_root / "sha256" / item[0][7:]).exists() for item in releases[:3])


def test_gc_deletes_nothing_when_active_state_is_indeterminate(tmp_path):
    cfg = config(tmp_path)
    release, manifest, payload, media, media_id = make_release()
    materialize(cfg, release, manifest, payload, media, media_id)
    write_pin(cfg.pin_path, release, actor="operator", reason="test")
    cfg.active_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.active_path.write_text("not-a-digest")
    obsolete = cfg.release_root / "sha256" / ("f" * 64)
    obsolete.mkdir(parents=True)
    (obsolete / "manifest.json").write_bytes(b"x")

    with pytest.raises(ActiveStateUnknown):
        LocalGarbageCollector(cfg).collect()
    assert obsolete.exists()


def test_gc_deletes_nothing_when_pin_state_is_indeterminate(tmp_path):
    cfg = config(tmp_path)
    release, manifest, payload, media, media_id = make_release()
    materialize(cfg, release, manifest, payload, media, media_id)
    cfg.active_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.active_path.write_text(release)
    cfg.pin_path.write_text("not-a-digest")
    obsolete = cfg.release_root / "sha256" / ("f" * 64)
    obsolete.mkdir(parents=True)
    (obsolete / "manifest.json").write_bytes(b"x")

    with pytest.raises(ActiveStateUnknown):
        LocalGarbageCollector(cfg).collect()
    assert obsolete.exists()
