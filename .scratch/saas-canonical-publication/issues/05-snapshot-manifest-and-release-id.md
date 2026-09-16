# T005 — Implement the snapshot manifest and release identity

Status: resolved
Type: implementation
Repository: `tiktok-analyzer-format-cards`
Blocked by: T01–T04 resolved

## Goal

Create the smallest runtime library that represents a project snapshot,
separates runtime from provenance, validates its schema, and verifies a pinned
release without a circular digest check.

## Files

- Create `publication/__init__.py`.
- Create `publication/manifest.py`.
- Create `publication/snapshot.schema.json`.
- Create `test_publication_manifest.py`.

## Interfaces

`publication.manifest` exposes:

```python
canonical_manifest_bytes(manifest: Mapping[str, object]) -> bytes
release_id_for(manifest: Mapping[str, object]) -> str
payload_digest(payload: bytes) -> str
verify_release(release_id: str, manifest: Mapping[str, object], payload: bytes) -> None
```

`release_id_for` hashes the canonical manifest with its `release_id` field
removed. Canonical JSON is UTF-8, `sort_keys=True`, compact separators,
`ensure_ascii=False`, and `allow_nan=False`; the canonicalization and hash
algorithm versions are explicit manifest fields.

## Acceptance criteria

- The schema requires `project_id`, `project_id_scheme`, `release_id`,
  `runtime`, and `provenance`.
- Runtime contains resolved compilation inputs; provenance contains
  `vault_commit`, `builder_version`, taxonomy/module digests, voice-profile
  digest, identity history, and build-time freshness.
- `verify_release` recomputes the manifest address without trusting the
  embedded `release_id`, then verifies the manifest's payload digest.
- Any manifest mutation, payload mutation, unsupported schema version, or
  non-canonical release ID fails explicitly.
- The test suite proves deterministic bytes, non-circular verification,
  Unicode handling, and rejection of NaN/unsupported values.

## Out of scope

R2 upload, Vault reading, identity allocation, SaaS authorization, and brief
compilation are handled by later tickets.

## Answer

Implemented in Analyzer commit `42f14fb`:

- Added the standard-library `publication.manifest` module with deterministic
  UTF-8 canonical JSON, `sha256:` payload digests, and non-circular release
  identity derived from the manifest without its embedded `release_id`.
- Added the v1 snapshot manifest schema with separate runtime/provenance
  requirements and version markers.
- Added five focused tests covering deterministic Unicode bytes, release
  identity, mutation rejection, payload verification, NaN, and unsupported
  versions.

Verification: `python -m unittest test_publication_manifest.py` passed 5/5;
the JSON schema parses successfully; independent spec-compliance and task-
quality review returned PASS/APPROVED with no findings. The existing
private-Vault gate failure when `VAULT_DIR` is absent is unrelated and remains
assigned to the later CI/release tickets.
