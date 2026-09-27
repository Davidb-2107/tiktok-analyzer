import hashlib
import json
import os
import re
import stat
import subprocess

import pytest
import vps.activation as activation_module

from publication.manifest import canonical_manifest_bytes, canonical_payload_bytes, release_id_for
from vps.activation import (
    ActivationConfig,
    ActivationLegacyRelease,
    ActiveStateUnknown,
    DigestMismatch,
    DockerGitInspector,
    GateNotPassed,
    HubUnreachable,
    ImageChanged,
    ImageNotAligned,
    IncompleteMaterialization,
    LocalGarbageCollector,
    MissingMedia,
    NotMaterialized,
    PinMismatch,
    ReleaseActivator,
)
from vps.release_sync import read_pin, write_pin

GATE_RUN_URL = "https://github.com/Davidb-2107/Wiki_Claude/actions/runs/1"


def gate_attestation(release, **overrides):
    record = {
        "schema_version": 1,
        "result": "pass",
        "release_id": release,
        "gate_run_id": "1",
        "gate_run_url": GATE_RUN_URL,
        "analyzer_ref": "a" * 40,
        "baseline_release_id": "sha256:" + "b" * 64,
        "vault_commit": "c" * 40,
    }
    record.update(overrides)
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")


def passing_gate(release):
    return lambda release_id: gate_attestation(release) if release_id == release else None


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


def test_reachability_accepts_http_errors_and_rejects_network_failures(monkeypatch):
    hub = activation_module.CommandHubController("unused", "https://example.test/hub")

    def http_502(request, timeout):
        raise activation_module.HTTPError(hub.external_url, 502, "Bad Gateway", {}, None)

    monkeypatch.setattr(activation_module, "urlopen", http_502)
    hub.check_reachable()

    def unresolved(request, timeout):
        raise activation_module.URLError("Name or service not known")

    monkeypatch.setattr(activation_module, "urlopen", unresolved)
    with pytest.raises(HubUnreachable):
        hub.check_reachable()


def test_reload_does_not_inject_a_static_source_context(monkeypatch):
    captured = {}

    def fake_run(command, *, check, env):
        captured["command"] = command
        captured["env"] = env

    monkeypatch.setenv("HUB_SOURCE_CONTEXT", "release:sha256:" + "b" * 64)
    monkeypatch.setattr(activation_module.subprocess, "run", fake_run)
    activation_module.CommandHubController("docker compose up", "https://example.test/hub").reload(
        "sha256:" + "a" * 64
    )

    assert "HUB_SOURCE_CONTEXT" not in captured["env"]


class Hub:
    def __init__(self):
        self.reloads = []
        self.verifications = []

    def reload(self, release_id):
        self.reloads.append(release_id)

    def verify_external(self, release_id):
        self.verifications.append(release_id)

    def check_reachable(self):
        pass


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

    activator = ReleaseActivator(cfg, hub, gate_reader=passing_gate(release), image_inspector=Inspector())
    assert activator.activate(release, actor="operator", reason="promote") == release
    assert read_pin(cfg.pin_path) == release
    assert cfg.active_path.read_text().strip() == release
    assert cfg.previous_path.read_text().strip() == "sha256:" + "1" * 64
    if os.name != "nt":
        assert stat.S_IMODE(cfg.active_path.stat().st_mode) == 0o640
    assert hub.reloads == [release]
    assert hub.verifications == [release]
    journal = [json.loads(line) for line in cfg.journal_path.read_text().splitlines()]
    assert journal[-1]["new"] == release
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z", journal[-1]["timestamp"])
    assert journal[-1]["gate_run"] == GATE_RUN_URL
    assert journal[-1]["image_revision"] == IMAGE_REVISION


def test_activation_refuses_before_any_change_when_hub_is_unreachable(tmp_path):
    cfg = config(tmp_path)
    release, manifest, payload, media, media_id = make_release()
    materialize(cfg, release, manifest, payload, media, media_id)
    write_pin(cfg.pin_path, release, actor="operator", reason="promote")
    cfg.active_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.active_path.write_text("sha256:" + "1" * 64)

    class UnreachableHub(Hub):
        def check_reachable(self):
            raise HubUnreachable("external Hub URL is unreachable")

    hub = UnreachableHub()
    with pytest.raises(HubUnreachable):
        ReleaseActivator(cfg, hub, gate_reader=passing_gate(release), image_inspector=Inspector()).activate(
            release, actor="operator", reason="promote"
        )
    assert cfg.active_path.read_text() == "sha256:" + "1" * 64
    assert not cfg.previous_path.exists()
    assert not cfg.journal_path.exists()
    assert hub.reloads == []


@pytest.mark.parametrize(
    "attestation",
    [
        None,
        b"not json",
        gate_attestation("sha256:" + "9" * 64),
        "fail",
        "schema",
        "no-url",
    ],
    ids=["absent", "malformed", "other-release", "not-pass", "unknown-schema", "no-run-url"],
)
def test_activation_requires_a_passing_gate_attestation(tmp_path, attestation):
    cfg = config(tmp_path)
    release, manifest, payload, media, media_id = make_release()
    materialize(cfg, release, manifest, payload, media, media_id)
    write_pin(cfg.pin_path, release, actor="operator", reason="promote")
    cfg.active_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.active_path.write_text("sha256:" + "1" * 64)
    attestation = {
        "fail": gate_attestation(release, result="fail"),
        "schema": gate_attestation(release, schema_version=2),
        "no-url": gate_attestation(release, gate_run_url=""),
    }.get(attestation, attestation)
    hub = Hub()

    with pytest.raises(GateNotPassed):
        ReleaseActivator(cfg, hub, gate_reader=lambda release_id: attestation).activate(
            release, actor="operator", reason="promote"
        )
    assert cfg.active_path.read_text() == "sha256:" + "1" * 64
    assert not cfg.previous_path.exists()
    assert not cfg.journal_path.exists()
    assert hub.reloads == []


def test_activation_without_a_gate_reader_fails_closed(tmp_path):
    cfg = config(tmp_path)
    release, manifest, payload, media, media_id = make_release()
    materialize(cfg, release, manifest, payload, media, media_id)
    write_pin(cfg.pin_path, release, actor="operator", reason="promote")

    with pytest.raises(GateNotPassed):
        ReleaseActivator(cfg, Hub()).activate(release, actor="operator", reason="promote")
    assert not cfg.active_path.exists()


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
    entry = [json.loads(line) for line in cfg.journal_path.read_text().splitlines()][-1]
    assert entry["gate_run"] is None
    assert entry["reason"] == "rollback: restore previous"


def test_public_activation_cannot_skip_the_gate(tmp_path):
    cfg = config(tmp_path)
    release, manifest, payload, media, media_id = make_release()
    materialize(cfg, release, manifest, payload, media, media_id)
    write_pin(cfg.pin_path, release, actor="operator", reason="promote")

    with pytest.raises(TypeError):
        ReleaseActivator(cfg, Hub()).activate(release, actor="operator", reason="promote", require_gate=False)
    with pytest.raises(TypeError):
        ReleaseActivator(cfg, Hub()).activate(release, actor="operator", reason="promote", gate_exempt=True)
    assert not cfg.active_path.exists()


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


ANALYZER_REF = "a" * 40
IMAGE_REVISION = "d" * 40


class Inspector:
    """Fake image inspector: container revisions are consumed in order, the last one sticks."""

    def __init__(self, container=(IMAGE_REVISION,), images=None, aligned=(IMAGE_REVISION,)):
        self.container = list(container)
        self.images = images or {}
        self.aligned_revisions = set(aligned)
        self.calls = []

    def revision(self, kind, ref):
        self.calls.append((kind, ref))
        if kind == "image":
            return self.images.get(ref)
        assert (kind, ref) == ("container", "tiktok-analyzer")
        value = self.container.pop(0) if len(self.container) > 1 else self.container[0]
        if isinstance(value, Exception):
            raise value
        return value

    def aligned(self, analyzer_ref, revision):
        assert analyzer_ref == ANALYZER_REF
        return revision in self.aligned_revisions


def ready(tmp_path):
    cfg = config(tmp_path)
    release, manifest, payload, media, media_id = make_release()
    materialize(cfg, release, manifest, payload, media, media_id)
    write_pin(cfg.pin_path, release, actor="operator", reason="promote")
    cfg.active_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.active_path.write_text("sha256:" + "1" * 64)
    return cfg, release


@pytest.mark.parametrize(
    "inspector",
    [None, Inspector(container=(None,)), Inspector(container=("not-a-sha",)), Inspector(container=("e" * 40,)), Inspector(container=(OSError("docker"),))],
    ids=["no-inspector", "no-label", "malformed-label", "not-aligned", "unreadable"],
)
def test_activation_refuses_before_any_change_without_an_aligned_image(tmp_path, inspector):
    cfg, release = ready(tmp_path)
    hub = Hub()

    with pytest.raises(ImageNotAligned):
        ReleaseActivator(cfg, hub, gate_reader=passing_gate(release), image_inspector=inspector).activate(
            release, actor="operator", reason="promote"
        )
    assert cfg.active_path.read_text() == "sha256:" + "1" * 64
    assert not cfg.previous_path.exists()
    assert not cfg.journal_path.exists()
    assert hub.reloads == []


@pytest.mark.parametrize("analyzer_ref", [None, "", "b469b32", "A" * 40], ids=["absent", "empty", "short", "uppercase"])
def test_activation_requires_a_full_analyzer_ref_in_the_attestation(tmp_path, analyzer_ref):
    cfg, release = ready(tmp_path)
    overrides = {"analyzer_ref": analyzer_ref}
    attestation = gate_attestation(release, **overrides)
    if analyzer_ref is None:
        record = json.loads(attestation)
        del record["analyzer_ref"]
        attestation = json.dumps(record).encode("utf-8")
    hub = Hub()

    with pytest.raises(GateNotPassed, match="analyzer_ref"):
        ReleaseActivator(cfg, hub, gate_reader=lambda release_id: attestation, image_inspector=Inspector()).activate(
            release, actor="operator", reason="promote"
        )
    assert hub.reloads == []


def test_image_change_during_reload_restores_pointers_and_is_not_masked(tmp_path):
    cfg, release = ready(tmp_path)
    old = "sha256:" + "1" * 64
    hub = Hub()
    inspector = Inspector(container=(IMAGE_REVISION, "e" * 40))

    with pytest.raises(ImageChanged, match="e{40} is not aligned") as raised:
        ReleaseActivator(cfg, hub, gate_reader=passing_gate(release), image_inspector=inspector).activate(
            release, actor="operator", reason="promote"
        )
    assert f"before: {IMAGE_REVISION}" in str(raised.value)
    assert cfg.active_path.read_text().strip() == old
    assert not cfg.previous_path.exists()
    assert hub.reloads == [release, old]
    assert hub.verifications == []
    assert not cfg.journal_path.exists()


def test_rollback_skips_alignment_and_journals_an_optional_revision(tmp_path):
    cfg = config(tmp_path)
    active, *active_rest = make_release("A")
    previous, *previous_rest = make_release("B")
    materialize(cfg, active, *active_rest)
    materialize(cfg, previous, *previous_rest)
    cfg.active_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.active_path.write_text(active)
    cfg.previous_path.write_text(previous)
    write_pin(cfg.pin_path, active, actor="operator", reason="promote")
    unaligned = Inspector(container=(OSError("docker"),), aligned=())

    ReleaseActivator(cfg, Hub(), image_inspector=unaligned).rollback(actor="operator", reason="restore previous")
    entry = [json.loads(line) for line in cfg.journal_path.read_text().splitlines()][-1]
    assert entry["new"] == previous
    assert entry["image_revision"] is None


def test_check_verifies_the_active_release_and_running_container(tmp_path):
    cfg, release = ready(tmp_path)
    cfg.active_path.write_text(release)
    hub = Hub()
    inspector = Inspector()

    result = ReleaseActivator(cfg, hub, gate_reader=passing_gate(release), image_inspector=inspector).check()
    assert result == {"active": release, "analyzer_ref": ANALYZER_REF, "image_revision": IMAGE_REVISION}
    assert inspector.calls == [("container", "tiktok-analyzer")]
    assert hub.verifications == [release]
    assert hub.reloads == []


def test_check_image_inspects_a_candidate_image_without_the_hub(tmp_path):
    cfg, release = ready(tmp_path)
    cfg.active_path.write_text(release)
    hub = Hub()
    inspector = Inspector(images={"tiktok-analyzer-hub": "e" * 40})
    activator = ReleaseActivator(cfg, hub, gate_reader=passing_gate(release), image_inspector=inspector)

    with pytest.raises(ImageNotAligned, match="image tiktok-analyzer-hub"):
        activator.check("tiktok-analyzer-hub")
    inspector.images["tiktok-analyzer-hub"] = IMAGE_REVISION
    assert activator.check("tiktok-analyzer-hub")["image_revision"] == IMAGE_REVISION
    assert ("container", "tiktok-analyzer") not in inspector.calls
    assert hub.verifications == []


def test_check_requires_the_active_release_attestation(tmp_path):
    cfg, release = ready(tmp_path)
    cfg.active_path.write_text(release)

    with pytest.raises(GateNotPassed):
        ReleaseActivator(cfg, Hub(), gate_reader=lambda release_id: None, image_inspector=Inspector()).check()


def test_docker_inspector_names_the_object_type(monkeypatch):
    seen = []

    class Result:
        stdout = json.dumps({"org.opencontainers.image.revision": IMAGE_REVISION})

    def fake_run(command, **kwargs):
        seen.append(command)
        return Result()

    monkeypatch.setattr(activation_module.subprocess, "run", fake_run)
    inspector = DockerGitInspector()
    assert inspector.revision("container", "tiktok-analyzer") == IMAGE_REVISION
    assert inspector.revision("image", "tiktok-analyzer-hub") == IMAGE_REVISION
    assert [command[2:4] for command in seen] == [["--type", "container"], ["--type", "image"]]


def _git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.test", "-c", "core.autocrlf=false", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(repo, path, content):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    _git(repo, "add", path)
    _git(repo, "commit", "-q", "-m", path)
    return _git(repo, "rev-parse", "HEAD")


def test_alignment_compares_only_image_inputs(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    gated = _commit(repo, "publication/manifest.py", "v1")
    vps_only = _commit(repo, "vps/activation.py", "check")
    ignore = _commit(repo, ".dockerignore", "temp")
    contract = _commit(repo, "publication/manifest.py", "v2")
    inspector = DockerGitInspector(repo)

    assert inspector.aligned(gated, gated)
    assert inspector.aligned(gated, vps_only)
    assert not inspector.aligned(gated, ignore)
    assert not inspector.aligned(vps_only, contract)
    with pytest.raises(ImageNotAligned, match="git fetch"):
        inspector.aligned(gated, "f" * 40)
