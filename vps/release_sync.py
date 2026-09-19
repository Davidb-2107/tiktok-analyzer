"""Prepare a pinned publication release from private R2.

This module only materializes content-addressed files. It never activates a
release and never mutates the object store.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from publication.manifest import parse_manifest_bytes, verify_release
from publication.media import media_object_key, require_media_digests, verify_media_bytes


LOG = logging.getLogger("tiktok_analyzer.release_sync")
_PIN = re.compile(r"sha256:[0-9a-f]{64}\Z")


class SyncError(RuntimeError):
    """A sync failure that must leave the active release untouched."""


class LegacyRelease(SyncError):
    """The pinned release predates the reconstructible media contract."""


class ObjectStore(Protocol):
    def get(self, key: str) -> bytes | None: ...


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SyncError(f"missing required environment variable: {name}")
    return value


def _digest_hex(release_id: str) -> str:
    if not isinstance(release_id, str) or _PIN.fullmatch(release_id) is None:
        raise SyncError("release pin is not canonical sha256:<lowercase-hex>")
    return release_id[7:]


def read_pin(path: Path) -> str:
    try:
        text = path.read_text(encoding="ascii")
    except OSError as error:
        raise SyncError(f"cannot read release pin: {path}") from error
    lines = text.splitlines()
    if len(lines) != 1 or _PIN.fullmatch(lines[0]) is None:
        raise SyncError("release pin must contain exactly one canonical digest line")
    return lines[0]


def _atomic_write(path: Path, data: bytes, mode: int = 0o640) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_pin(path: Path, digest: str, *, actor: str, reason: str) -> None:
    """Write the operator-owned pin and append its audit record."""
    _digest_hex(digest)
    if not actor.strip() or not reason.strip():
        raise SyncError("pin actor and reason are required")
    old = None
    if path.exists():
        old = read_pin(path)
    _atomic_write(path, (digest + "\n").encode("ascii"), mode=0o600)
    journal = path.with_name(path.name + ".journal")
    entry = {"actor": actor, "old": old, "new": digest, "reason": reason, "timestamp": _now()}
    with journal.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
    os.chmod(journal, 0o600)


class S3ObjectStore:
    """The deliberately tiny R2 adapter: GET only, with no listing client."""

    def __init__(self, *, endpoint: str, bucket: str, region: str, access_key: str, secret_key: str):
        try:
            import boto3
        except ImportError as error:
            raise SyncError("boto3 is required for release sync") from error
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    def get(self, key: str) -> bytes | None:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except Exception as error:  # boto3 keeps ClientError optional at import time.
            code = str(getattr(error, "response", {}).get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise SyncError(f"R2 GET failed for {key}: {error}") from error
        body = response.get("Body")
        if body is None:
            raise SyncError(f"R2 GET returned no body for {key}")
        return body.read()


@dataclass(frozen=True)
class SyncConfig:
    pin_path: Path
    state_path: Path
    release_root: Path
    media_root: Path
    endpoint: str
    bucket: str
    prefix: str
    region: str
    access_key: str
    secret_key: str
    notify_command: str | None = None

    @classmethod
    def from_env(cls) -> "SyncConfig":
        region = _require_env("RELEASE_R2_REGION")
        if region != "auto":
            raise SyncError("RELEASE_R2_REGION must be auto")
        prefix = _require_env("RELEASE_R2_PREFIX")
        if prefix != "releases/":
            raise SyncError("RELEASE_R2_PREFIX must be releases/")
        state_root = Path(os.environ.get("RELEASE_SYNC_STATE_ROOT", "/var/lib/tiktok-analyzer/release-sync"))
        return cls(
            pin_path=Path(os.environ.get("RELEASE_SYNC_PIN_PATH", state_root / "pinned-release")),
            state_path=Path(os.environ.get("RELEASE_SYNC_STATE_PATH", state_root / "state.json")),
            release_root=Path(_require_env("RELEASE_SYNC_RELEASE_ROOT")),
            media_root=Path(_require_env("RELEASE_SYNC_MEDIA_ROOT")),
            endpoint=_require_env("RELEASE_R2_ENDPOINT"),
            bucket=_require_env("RELEASE_R2_BUCKET"),
            prefix=prefix,
            region=region,
            access_key=_require_env("RELEASE_R2_READ_ACCESS_KEY_ID"),
            secret_key=_require_env("RELEASE_R2_READ_SECRET_ACCESS_KEY"),
            notify_command=os.environ.get("RELEASE_SYNC_NOTIFY_COMMAND") or None,
        )


def _load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"consecutive_failures": 0}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError(f"cannot read sync state: {path}") from error
    if not isinstance(value, dict):
        raise SyncError("sync state must be a JSON object")
    return value


def _write_state(path: Path, state: Mapping[str, object]) -> None:
    _atomic_write(path, (json.dumps(state, sort_keys=True, indent=2) + "\n").encode("utf-8"))


def _safe_file(path: Path) -> None:
    info = path.lstat()
    unsafe_mode = os.name != "nt" and (not (info.st_mode & 0o400) or info.st_mode & 0o022)
    if not path.is_file() or path.is_symlink() or unsafe_mode:
        raise SyncError(f"unsafe materialized file permissions: {path}")


def _write_staged(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chmod(path, 0o640)
    _safe_file(path)


def _same_file(path: Path, data: bytes) -> bool:
    _safe_file(path)
    return path.read_bytes() == data


def _materialize_file(destination: Path, data: bytes) -> None:
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        os.chmod(temporary, 0o640)
        _safe_file(temporary)
        os.replace(temporary, destination)
        if not _same_file(destination, data):
            raise SyncError(f"materialized bytes changed: {destination}")
    finally:
        temporary.unlink(missing_ok=True)


class ReleaseSync:
    def __init__(self, config: SyncConfig, store: ObjectStore, notifier: Callable[[Mapping[str, object]], None] | None = None):
        self.config = config
        self.store = store
        self.notifier = notifier

    def _notify(self, event: Mapping[str, object]) -> None:
        try:
            if self.notifier is not None:
                self.notifier(event)
            elif self.config.notify_command:
                subprocess.run(shlex.split(self.config.notify_command), input=json.dumps(event, sort_keys=True), text=True, check=False)
        except Exception as error:  # Notifications must not change sync safety.
            LOG.error("release sync notification failed: %s", error)

    def run(self) -> bool:
        state = _load_state(self.config.state_path)
        started = _now()
        pinned = state.get("pin")
        try:
            pinned = read_pin(self.config.pin_path)
            self.prepare(pinned)
        except Exception as error:
            failures = int(state.get("consecutive_failures", 0)) + 1
            state.update({"pin": pinned, "last_attempt_at": started, "last_error": str(error), "consecutive_failures": failures})
            _write_state(self.config.state_path, state)
            if failures == 2:
                self._notify({"event": "sync_failure", "consecutive_failures": failures, "error": str(error)})
                LOG.critical("RELEASE_SYNC_ALERT failures=%s error=%s", failures, error)
            return False

        previous_failures = int(state.get("consecutive_failures", 0))
        state.update({"pin": pinned, "last_attempt_at": started, "last_success_at": _now(), "last_error": None, "materialized_digest": pinned, "consecutive_failures": 0})
        _write_state(self.config.state_path, state)
        if previous_failures >= 2:
            self._notify({"event": "sync_recovered", "pin": pinned})
        return True

    def prepare(self, release_id: str) -> None:
        digest = _digest_hex(release_id)
        prefix = f"{self.config.prefix}sha256/{digest}"
        manifest_key, payload_key = f"{prefix}/manifest.json", f"{prefix}/payload.json"
        manifest_bytes, payload_bytes = self.store.get(manifest_key), self.store.get(payload_key)
        if manifest_bytes is None or payload_bytes is None:
            missing = manifest_key if manifest_bytes is None else payload_key
            raise SyncError(f"release object is missing: {missing}")
        try:
            verify_release(release_id, manifest_bytes, payload_bytes)
            manifest = parse_manifest_bytes(manifest_bytes)
            records = require_media_digests(manifest)
        except ValueError as error:
            if str(error).startswith("legacy release is not reconstructible"):
                raise LegacyRelease(str(error)) from error
            raise SyncError(str(error)) from error

        media: list[tuple[dict[str, object], bytes]] = []
        for record in records:
            key = media_object_key(record["media_id"], record["extension"], prefix="releases/media")
            data = self.store.get(key)
            try:
                verify_media_bytes(record, data)
            except ValueError as error:
                raise SyncError(str(error)) from error
            media.append((record, data))  # type: ignore[arg-type]

        release_root = self.config.release_root / "sha256"
        release_root.mkdir(parents=True, exist_ok=True)
        self.config.media_root.mkdir(parents=True, exist_ok=True)
        target = release_root / digest
        for record, data in media:
            destination = self.config.media_root / f"{record['media_id']}{record['extension']}"
            if destination.exists() and not _same_file(destination, data):
                raise SyncError(f"materialized media collision: {destination.name}")

        temporary = Path(tempfile.mkdtemp(prefix=".release-sync-", dir=str(self.config.release_root)))
        try:
            staged_release = temporary / "sha256" / digest
            _write_staged(staged_release / "manifest.json", manifest_bytes)
            _write_staged(staged_release / "payload.json", payload_bytes)
            if target.exists():
                if target.is_symlink():
                    raise SyncError(f"unsafe materialized release path: {target}")
                if not target.is_dir() or {item.name for item in target.iterdir()} != {"manifest.json", "payload.json"} or not _same_file(target / "manifest.json", manifest_bytes) or not _same_file(target / "payload.json", payload_bytes):
                    raise SyncError(f"materialized release collision: {release_id}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                staged_release.rename(target)
            for record, data in media:
                destination = self.config.media_root / f"{record['media_id']}{record['extension']}"
                if destination.exists():
                    continue
                staged_media = temporary / f"{record['media_id']}{record['extension']}"
                _write_staged(staged_media, data)
                destination.parent.mkdir(parents=True, exist_ok=True)
                _materialize_file(destination, staged_media.read_bytes())
        finally:
            shutil.rmtree(temporary, ignore_errors=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    pin = subparsers.add_parser("pin", help="write the operator-owned release pin")
    pin.add_argument("--path", type=Path, default=None)
    pin.add_argument("--digest", required=True)
    pin.add_argument("--actor", required=True)
    pin.add_argument("--reason", required=True)
    subparsers.add_parser("sync", help="materialize the pinned release")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    args = _build_parser().parse_args(argv)
    if args.command == "pin":
        path = args.path or Path(os.environ.get("RELEASE_SYNC_PIN_PATH", "/var/lib/tiktok-analyzer/release-sync/pinned-release"))
        write_pin(path, args.digest, actor=args.actor, reason=args.reason)
        return 0
    config = SyncConfig.from_env()
    store = S3ObjectStore(endpoint=config.endpoint, bucket=config.bucket, region=config.region, access_key=config.access_key, secret_key=config.secret_key)
    return 0 if ReleaseSync(config, store).run() else 1


if __name__ == "__main__":
    raise SystemExit(main())
