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

## Contract revision after review

The first implementation was faithful to the original brief, but the brief
did not define the hashed payload or an interoperable canonicalization. This
revision is part of T005 and must land before T009:

- `manifest.json` is the release-identity/provenance object; `payload.json` is
  a separate immutable canonical JSON object containing `runtime` only. The
  manifest does not duplicate runtime. `payload_digest` hashes the canonical
  payload bytes.
- `json-c14n-v1` is a restricted format: ASCII string keys only, UTF-8-byte
  lexicographic ordering, NFC strings, no floats/NaN/infinity/negative zero,
  and duplicate-key rejection. Fields declared `decimal-v1` use the exact
  normalized grammar `^-?(0|[1-9][0-9]*)(\\.[0-9]*[1-9])?$`; `215.0`, `215`,
  and `215.00` therefore publish as `"215"`, and `1.5` as `"1.5"`. Both
  stored objects must already be canonical. Builders normalize from exact
  decimal input, never binary floats.
- Versioned known-answer vectors are required for key order, NFC, numeric
  rejection/decimal strings, duplicate keys, and exact bytes.
- Provenance names are exact: `vault_commit`, `builder_version`,
  `taxonomy_module_digest`, `module_digests`, `sot_versions`,
  `voice_profile_digest`, `identity_history`, and `build_freshness`.
- The reader exposes a strict manifest-bytes entry point. It rejects duplicate
  keys, non-canonical bytes, and payloads that do not satisfy the declared
  runtime schema before release verification.

## Interfaces

`publication.manifest` exposes:

```python
canonical_manifest_bytes(manifest: Mapping[str, object]) -> bytes
canonical_payload_bytes(payload: Mapping[str, object]) -> bytes
parse_manifest_bytes(data: bytes) -> Mapping[str, object]
release_id_for(manifest: Mapping[str, object]) -> str
payload_digest(payload: bytes) -> str
verify_release(release_id: str, manifest: Mapping[str, object], payload: bytes) -> None
```

`release_id_for` hashes the canonical manifest with its `release_id` field
removed. `verify_release` receives canonical `payload.json` bytes, not an
unspecified duplicate of the runtime. The canonicalization and hash algorithm
versions are explicit manifest fields.

## Acceptance criteria

- The manifest schema requires `project_id`, `project_id_scheme`,
  `release_id`, `payload_digest`, and `provenance`; the payload schema requires
  the runtime object and its resolved compilation inputs.
- Provenance contains `vault_commit`, `builder_version`,
  `taxonomy_module_digest`, `module_digests`, `sot_versions`,
  `voice_profile_digest`, `identity_history`, and `build_freshness`.
- `verify_release` recomputes the manifest address without trusting the
  embedded `release_id`, then verifies the manifest's payload digest.
- Any manifest mutation, payload mutation, unsupported schema version, or
  non-canonical release ID fails explicitly.
- The test suite proves deterministic bytes, non-circular verification,
  Unicode NFC handling, duplicate-key rejection, known-answer vectors, and
  rejection of floats/NaN/unsupported values.

## Out of scope

R2 upload, Vault reading, identity allocation, SaaS authorization, and brief
compilation are handled by later tickets.

## Previous implementation record

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

## Answer

The review revision is resolved in Analyzer commits `db61997`, `6309628`, and
`f797713`:

- `manifest.json` and `payload.json` are separate; the payload is canonical
  runtime JSON and the manifest carries only its digest plus provenance.
- `json-c14n-v1` is restricted and interoperable: ASCII key ordering, NFC
  strings, integer-only JSON numbers, canonical decimal strings, compact UTF-8,
  duplicate-key rejection, and versioned known-answer vectors.
- Stored manifest and payload bytes are parsed strictly, validated against the
  declared shape, and rejected when non-canonical or incomplete.
- Focused verification passes **14/14** tests; `git diff --check` and schema
  parsing pass. Independent re-review: spec compliance PASS; the stale test
  count in the local SDD report was corrected from 11 to 12.
