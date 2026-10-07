"""Explicit activation, rollback, and local garbage collection for releases."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from publication.manifest import parse_manifest_bytes, verify_release
from publication.media import MEDIA_EXTENSIONS, require_media_digests, verify_media_bytes
from publication.release_state import ReleaseStateError, read_release_state
from publication.source import parse_source_context, resolve_source
from vps.release_sync import (
    ReleaseSync,
    S3ObjectStore,
    SyncConfig,
    SyncError,
    _atomic_write,
    _digest_hex,
    _now,
    _safe_file,
    read_pin,
    write_pin,
)

LOG = logging.getLogger("tiktok_analyzer.activation")
_COMMIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
# Everything that can reach the Hub image build context (ADR 0007).
_IMAGE_INPUTS = ("Dockerfile.prod", ".dockerignore", ".gitattributes", "backend", "publication", "frontend")
_HUB_CONTAINER = "tiktok-analyzer"
_REVISION_LABEL = "org.opencontainers.image.revision"
_MEDIA_NAME = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}(?:" + "|".join(re.escape(ext) for ext in MEDIA_EXTENSIONS) + r")\Z"
)


class ActivationError(RuntimeError):
    """A requested activation cannot safely change the served release."""


class PinMismatch(ActivationError):
    pass


class NotMaterialized(ActivationError):
    pass


class IncompleteMaterialization(ActivationError):
    pass


class ActivationLegacyRelease(ActivationError):
    pass


class MissingMedia(ActivationError):
    pass


class DigestMismatch(ActivationError):
    pass


class ActiveStateUnknown(ActivationError):
    pass


class RollbackUnavailable(ActivationError):
    pass


class RollbackPreparationFailed(ActivationError):
    pass


class ServingMismatch(ActivationError):
    pass


class HubUnreachable(ActivationError):
    pass


class GateNotPassed(ActivationError):
    pass


class ImageNotAligned(ActivationError):
    pass


class ImageChanged(ActivationError):
    """The Hub image changed during reload; only the release pointers were restored."""


class HubController(Protocol):
    def reload(self, release_id: str) -> None: ...

    def verify_external(self, release_id: str) -> None: ...

    def check_reachable(self) -> None: ...


class ImageInspector(Protocol):
    def revision(self, kind: str, ref: str) -> str | None: ...

    def aligned(self, analyzer_ref: str, revision: str) -> bool: ...


@dataclass(frozen=True)
class ActivationConfig:
    pin_path: Path
    active_path: Path
    previous_path: Path
    journal_path: Path
    release_root: Path
    media_root: Path
    reload_command: str | None
    external_url: str | None

    @classmethod
    def from_env(cls, *, require_hub: bool = True) -> ActivationConfig:
        state_root = Path(os.environ.get("RELEASE_SYNC_STATE_ROOT", "/var/lib/tiktok-analyzer/release-sync"))
        release_root = os.environ.get("RELEASE_SYNC_RELEASE_ROOT", "")
        media_root = os.environ.get("RELEASE_SYNC_MEDIA_ROOT", "")
        if not release_root or not media_root:
            raise ActivationError("RELEASE_SYNC_RELEASE_ROOT and RELEASE_SYNC_MEDIA_ROOT are required")
        reload_command = os.environ.get("RELEASE_ACTIVATE_RELOAD_COMMAND") or None
        external_url = os.environ.get("RELEASE_ACTIVATE_EXTERNAL_URL") or None
        if require_hub and (not reload_command or not external_url):
            raise ActivationError("RELEASE_ACTIVATE_RELOAD_COMMAND and RELEASE_ACTIVATE_EXTERNAL_URL are required")
        return cls(
            pin_path=Path(os.environ.get("RELEASE_SYNC_PIN_PATH", state_root / "pinned-release")),
            active_path=Path(os.environ.get("RELEASE_ACTIVATE_ACTIVE_PATH", state_root / "active-release")),
            previous_path=Path(os.environ.get("RELEASE_ACTIVATE_PREVIOUS_PATH", state_root / "previous-release")),
            journal_path=Path(os.environ.get("RELEASE_ACTIVATE_JOURNAL_PATH", state_root / "activation.journal")),
            release_root=Path(release_root),
            media_root=Path(media_root),
            reload_command=reload_command,
            external_url=external_url,
        )


def _read_state(path: Path, label: str, *, required: bool) -> str | None:
    try:
        return read_release_state(path, label=label, required=required)
    except ReleaseStateError as error:
        raise ActiveStateUnknown(str(error)) from error


def _write_state(path: Path, release_id: str | None) -> None:
    if release_id is None:
        if path.is_symlink():
            raise ActiveStateUnknown(f"cannot remove symlink state: {path}")
        path.unlink(missing_ok=True)
        return
    _digest_hex(release_id)
    _atomic_write(path, (release_id + "\n").encode("ascii"), mode=0o640)


def _restore_state(path: Path, release_id: str | None) -> None:
    _write_state(path, release_id)


def _validate_local_release(
    config: ActivationConfig, release_id: str
) -> tuple[Mapping[str, object], list[dict[str, object]]]:
    digest = _digest_hex(release_id)
    directory = config.release_root / "sha256" / digest
    if not directory.exists():
        raise NotMaterialized(f"release is not materialized: {release_id}")
    if directory.is_symlink() or not directory.is_dir():
        raise IncompleteMaterialization(f"release materialization is not a directory: {release_id}")
    if {item.name for item in directory.iterdir()} != {"manifest.json", "payload.json"}:
        raise IncompleteMaterialization(f"release materialization is incomplete: {release_id}")
    manifest_path, payload_path = directory / "manifest.json", directory / "payload.json"
    try:
        _safe_file(manifest_path)
        _safe_file(payload_path)
        manifest_bytes, payload_bytes = manifest_path.read_bytes(), payload_path.read_bytes()
    except (OSError, SyncError) as error:
        raise IncompleteMaterialization(f"release materialization is unreadable: {release_id}") from error
    try:
        verify_release(release_id, manifest_bytes, payload_bytes)
        manifest = parse_manifest_bytes(manifest_bytes)
        records = require_media_digests(manifest)
    except ValueError as error:
        if str(error).startswith("legacy release is not reconstructible"):
            raise ActivationLegacyRelease(str(error)) from error
        raise DigestMismatch(f"release digest validation failed: {release_id}") from error

    for record in records:
        media_path = config.media_root / f"{record['media_id']}{record['extension']}"
        if not media_path.exists():
            raise MissingMedia(f"media is missing: {record['media_id']}")
        try:
            _safe_file(media_path)
            verify_media_bytes(record, media_path.read_bytes())
        except ValueError as error:
            raise DigestMismatch(str(error)) from error
        except (OSError, SyncError) as error:
            raise IncompleteMaterialization(f"media materialization is unreadable: {record['media_id']}") from error

    try:
        resolve_source(parse_source_context(f"release:{release_id}"), release_root=config.release_root)
    except ValueError as error:
        raise IncompleteMaterialization(f"Hub cannot load materialized release: {release_id}") from error
    return manifest, records


def _append_journal(path: Path, entry: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(entry), sort_keys=True, separators=(",", ":")) + "\n")
    os.chmod(path, 0o640)


class ReleaseActivator:
    def __init__(
        self,
        config: ActivationConfig,
        hub: HubController,
        sync_runner: Callable[[], bool] | None = None,
        gate_reader: Callable[[str], bytes | None] | None = None,
        image_inspector: ImageInspector | None = None,
    ):
        self.config = config
        self.hub = hub
        self.sync_runner = sync_runner
        self.gate_reader = gate_reader
        self.image_inspector = image_inspector

    def activate(self, release_id: str, *, actor: str, reason: str) -> str:
        return self._activate(release_id, actor=actor, reason=reason, gate_exempt=False)

    def _activate(self, release_id: str, *, actor: str, reason: str, gate_exempt: bool) -> str:
        if not actor.strip() or not reason.strip():
            raise ActivationError("activation actor and reason are required")
        try:
            pinned = read_pin(self.config.pin_path)
        except SyncError as error:
            raise PinMismatch("cannot activate without a readable release pin") from error
        if release_id != pinned:
            raise PinMismatch(f"target digest is not pinned: {release_id}")
        _validate_local_release(self.config, release_id)
        active = _read_state(self.config.active_path, "active", required=False)
        if active == release_id:
            try:
                self.hub.verify_external(release_id)
            except Exception as error:
                raise ServingMismatch(f"Hub does not serve requested release: {release_id}") from error
            self._audit(active, release_id, actor, reason, idempotent=True, image_revision=self._optional_revision())
            return release_id

        gate_run = analyzer_ref = image_revision = None
        if not gate_exempt:
            gate_run, analyzer_ref = self._require_gate(release_id)
            image_revision = self._require_aligned_image(analyzer_ref)
        # The post-reload check needs the external URL; refuse before touching
        # state or recreating the Hub if this shell cannot reach it at all.
        self.hub.check_reachable()
        previous = _read_state(self.config.previous_path, "previous", required=False)
        try:
            _write_state(self.config.active_path, release_id)
            _write_state(self.config.previous_path, active)
        except Exception as error:
            try:
                _restore_state(self.config.active_path, active)
                _restore_state(self.config.previous_path, previous)
            except Exception as restore_error:
                raise ActiveStateUnknown("activation state could not be restored") from restore_error
            raise ActivationError("active state could not be written") from error
        try:
            self.hub.reload(release_id)
            if analyzer_ref is not None:
                # Detection only: a mismatch restores the release pointers,
                # not the previous image; the operator must redeploy it.
                image_revision = self._require_aligned_image(
                    analyzer_ref, error=ImageChanged, context=f"after reload (before: {image_revision})"
                )
            self.hub.verify_external(release_id)
        except Exception as error:
            try:
                _restore_state(self.config.active_path, active)
                _restore_state(self.config.previous_path, previous)
                if active is not None:
                    self.hub.reload(active)
            except Exception as restore_error:
                raise ActiveStateUnknown("activation failed and active state could not be restored") from restore_error
            if isinstance(error, (ServingMismatch, ImageChanged)):
                raise
            raise ServingMismatch(f"Hub did not serve requested release: {release_id}") from error
        if gate_exempt:
            image_revision = self._optional_revision()
        self._audit(
            active, release_id, actor, reason, idempotent=False, gate_run=gate_run, image_revision=image_revision
        )
        return release_id

    def check(self, image: str | None = None) -> dict[str, str]:
        """Read-only: is the active release gated and served by an aligned image?"""
        active = _read_state(self.config.active_path, "active", required=True)
        assert active is not None
        _, analyzer_ref = self._require_gate(active)
        if image is not None:
            revision = self._require_aligned_image(analyzer_ref, kind="image", ref=image)
        else:
            revision = self._require_aligned_image(analyzer_ref)
            try:
                self.hub.verify_external(active)
            except Exception as error:
                raise ServingMismatch(f"Hub does not serve the active release: {active}") from error
        return {"active": active, "analyzer_ref": analyzer_ref, "image_revision": revision}

    def rollback(self, *, actor: str, reason: str) -> str:
        active = _read_state(self.config.active_path, "active", required=True)
        target = _read_state(self.config.previous_path, "previous", required=True)
        assert active is not None and target is not None
        write_pin(self.config.pin_path, target, actor=actor, reason=f"rollback: {reason}")
        try:
            _validate_local_release(self.config, target)
        except NotMaterialized:
            try:
                prepared = self.sync_runner is not None and self.sync_runner()
            except Exception as error:
                raise RollbackPreparationFailed(f"rollback preparation failed: {target}") from error
            if not prepared:
                raise RollbackPreparationFailed(f"rollback release is not materialized: {target}")
            _validate_local_release(self.config, target)
        # Only rollback may skip the gate: it restores the previous active
        # release, which may predate gate attestations. The journal records it
        # with gate_run null and a "rollback: " reason (ADR 0005).
        return self._activate(target, actor=actor, reason=f"rollback: {reason}", gate_exempt=True)

    def _require_gate(self, release_id: str) -> tuple[str, str]:
        if self.gate_reader is None:
            raise GateNotPassed("no gate attestation reader is configured")
        try:
            data = self.gate_reader(release_id)
        except Exception as error:
            raise GateNotPassed(f"gate attestation is unreadable: {release_id}") from error
        if data is None:
            raise GateNotPassed(f"no passing private gate is recorded for {release_id}")
        try:
            record = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise GateNotPassed(f"gate attestation is malformed: {release_id}") from error
        if (
            not isinstance(record, Mapping)
            or record.get("schema_version") != 1
            or record.get("result") != "pass"
            or record.get("release_id") != release_id
            or not isinstance(record.get("gate_run_url"), str)
            or not record["gate_run_url"].strip()
        ):
            raise GateNotPassed(f"gate attestation does not record a pass for {release_id}")
        analyzer_ref = record.get("analyzer_ref")
        if not isinstance(analyzer_ref, str) or not _COMMIT_SHA.fullmatch(analyzer_ref):
            raise GateNotPassed(f"gate attestation has no valid analyzer_ref for {release_id}")
        return record["gate_run_url"], analyzer_ref

    def _require_aligned_image(
        self,
        analyzer_ref: str,
        *,
        kind: str = "container",
        ref: str = _HUB_CONTAINER,
        error: type[ActivationError] = ImageNotAligned,
        context: str = "",
    ) -> str:
        where = f"{kind} {ref}" + (f" {context}" if context else "")
        if self.image_inspector is None:
            raise error("no image inspector is configured")
        try:
            revision = self.image_inspector.revision(kind, ref)
        except Exception as cause:
            raise error(f"cannot read the {_REVISION_LABEL} label of {where}") from cause
        if not isinstance(revision, str) or not _COMMIT_SHA.fullmatch(revision):
            raise error(f"{where} carries no valid {_REVISION_LABEL} label: {revision!r}")
        try:
            aligned = self.image_inspector.aligned(analyzer_ref, revision)
        except Exception as cause:
            raise error(f"cannot compare {where} revision {revision} with {analyzer_ref}: {cause}") from cause
        if not aligned:
            raise error(f"{where} revision {revision} is not aligned with gate analyzer_ref {analyzer_ref}")
        return revision

    def _optional_revision(self) -> str | None:
        # Journal only: a rollback must not fail on an unreadable label.
        try:
            return self.image_inspector.revision("container", _HUB_CONTAINER) if self.image_inspector else None
        except Exception:
            return None

    def _audit(
        self,
        old: str | None,
        new: str,
        actor: str,
        reason: str,
        *,
        idempotent: bool,
        gate_run: str | None = None,
        image_revision: str | None = None,
    ) -> None:
        _append_journal(
            self.config.journal_path,
            {
                "actor": actor,
                "old": old,
                "new": new,
                "reason": reason,
                "idempotent": idempotent,
                "gate_run": gate_run,
                "image_revision": image_revision,
                "timestamp": _now(),
            },
        )


class CommandHubController:
    def __init__(self, reload_command: str, external_url: str, timeout: float = 15.0):
        self.reload_command = reload_command
        self.external_url = external_url
        self.timeout = timeout

    def reload(self, release_id: str) -> None:
        environment = os.environ.copy()
        environment.pop("HUB_SOURCE_CONTEXT", None)
        subprocess.run(shlex.split(self.reload_command), check=True, env=environment)

    def check_reachable(self) -> None:
        # Any HTTP answer (even 502) proves the network path; only a transport
        # failure (DNS, route, timeout) means activation cannot verify from here.
        request = Request(self.external_url, headers={"User-Agent": "tiktok-analyzer-activation/1"})
        try:
            with urlopen(request, timeout=self.timeout):
                pass
        except HTTPError:
            pass
        except (URLError, OSError) as error:
            raise HubUnreachable(f"external Hub URL is unreachable from this host: {self.external_url}") from error

    def verify_external(self, release_id: str) -> None:
        request = Request(
            self.external_url,
            headers={"Accept": "application/json", "User-Agent": "tiktok-analyzer-activation/1"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise ServingMismatch(f"external Hub check failed: {self.external_url}") from error
        if not isinstance(payload, Mapping) or payload.get("release_id") != release_id:
            raise ServingMismatch(f"external Hub serves a different release than {release_id}")


class DockerGitInspector:
    """Reads the Hub revision label from Docker and compares image inputs in this checkout."""

    def __init__(self, repo: Path | None = None):
        self.repo = repo or Path(__file__).resolve().parents[1]

    def revision(self, kind: str, ref: str) -> str | None:
        # --type is explicit: an image and a container may share a name.
        result = subprocess.run(
            ["docker", "inspect", "--type", kind, "--format", "{{json .Config.Labels}}", ref],
            check=True,
            capture_output=True,
            text=True,
        )
        labels = json.loads(result.stdout) or {}
        return labels.get(_REVISION_LABEL)

    def aligned(self, analyzer_ref: str, revision: str) -> bool:
        for sha in (analyzer_ref, revision):
            if self._git("cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
                raise ImageNotAligned(f"commit {sha} is not in {self.repo}; run git fetch")
        diff = self._git("diff", "--quiet", analyzer_ref, revision, "--", *_IMAGE_INPUTS)
        if diff.returncode not in (0, 1):
            raise ImageNotAligned(f"git diff failed in {self.repo}: {diff.stderr.strip()}")
        return diff.returncode == 0

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=False)


class LocalGarbageCollector:
    def __init__(self, config: ActivationConfig):
        self.config = config

    def collect(self) -> dict[str, int]:
        active = _read_state(self.config.active_path, "active", required=True)
        previous = _read_state(self.config.previous_path, "previous", required=False)
        try:
            pinned = read_pin(self.config.pin_path)
        except SyncError as error:
            raise ActiveStateUnknown("pin state is indeterminate") from error
        assert active is not None
        protected = {active, pinned}
        if previous is not None:
            protected.add(previous)
        referenced_media: set[str] = set()
        for release_id in (active, previous, pinned):
            if release_id is None:
                continue
            directory = self.config.release_root / "sha256" / release_id[7:]
            if not directory.exists():
                if release_id == active or release_id == previous:
                    raise ActiveStateUnknown(f"protected release is not materialized: {release_id}")
                continue
            try:
                _, records = _validate_local_release(self.config, release_id)
            except ActivationError as error:
                raise ActiveStateUnknown(f"protected release is not safely readable: {release_id}") from error
            referenced_media.update(f"{record['media_id']}{record['extension']}" for record in records)

        deleted_releases = 0
        release_directory = self.config.release_root / "sha256"
        if release_directory.exists():
            for candidate in release_directory.iterdir():
                if not re.fullmatch(r"[0-9a-f]{64}", candidate.name) or candidate.name in {
                    item[7:] for item in protected
                }:
                    continue
                if (
                    candidate.is_symlink()
                    or not candidate.is_dir()
                    or {item.name for item in candidate.iterdir()} != {"manifest.json", "payload.json"}
                    or any(item.is_symlink() or not item.is_file() for item in candidate.iterdir())
                ):
                    continue
                shutil.rmtree(candidate)
                deleted_releases += 1

        deleted_media = 0
        if self.config.media_root.exists():
            for candidate in self.config.media_root.iterdir():
                if (
                    not _MEDIA_NAME.fullmatch(candidate.name)
                    or candidate.name in referenced_media
                    or candidate.is_symlink()
                    or not candidate.is_file()
                ):
                    continue
                candidate.unlink()
                deleted_media += 1
        return {"deleted_releases": deleted_releases, "deleted_media": deleted_media}


def _sync_runner() -> Callable[[], bool]:
    def run() -> bool:
        config = SyncConfig.from_env()
        store = S3ObjectStore(
            endpoint=config.endpoint,
            bucket=config.bucket,
            region=config.region,
            access_key=config.access_key,
            secret_key=config.secret_key,
        )
        return ReleaseSync(config, store).run()

    return run


def _gate_reader() -> Callable[[str], bytes | None]:
    def read(release_id: str) -> bytes | None:
        config = SyncConfig.from_env()
        store = S3ObjectStore(
            endpoint=config.endpoint,
            bucket=config.bucket,
            region=config.region,
            access_key=config.access_key,
            secret_key=config.secret_key,
        )
        return store.get(f"{config.prefix}gates/sha256/{_digest_hex(release_id)}.json")

    return read


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    activate = subparsers.add_parser("activate")
    activate.add_argument("--digest", required=True)
    activate.add_argument("--actor", required=True)
    activate.add_argument("--reason", required=True)
    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--actor", required=True)
    rollback.add_argument("--reason", required=True)
    subparsers.add_parser("gc")
    check = subparsers.add_parser("check")
    check.add_argument("--image", help="check a built image before deploying it instead of the running container")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    args = _parser().parse_args(argv)
    try:
        if args.command == "gc":
            print(
                json.dumps(
                    LocalGarbageCollector(ActivationConfig.from_env(require_hub=False)).collect(), sort_keys=True
                )
            )
            return 0
        config = ActivationConfig.from_env()
        hub = CommandHubController(config.reload_command, config.external_url)
        activator = ReleaseActivator(
            config, hub, _sync_runner() if args.command == "rollback" else None, _gate_reader(), DockerGitInspector()
        )
        if args.command == "check":
            print(json.dumps(activator.check(args.image), sort_keys=True))
        elif args.command == "activate":
            activator.activate(args.digest, actor=args.actor, reason=args.reason)
        else:
            activator.rollback(actor=args.actor, reason=args.reason)
        return 0
    except ActivationError as error:
        LOG.error("%s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
