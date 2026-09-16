# SaaS Canonical Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Analyzer consumption from implicit Vault access to reproducible, pinned project snapshots while preserving channel isolation and deterministic mapping.

**Architecture:** A trusted Vault publisher creates one immutable project snapshot with one project-level mapping and channel-scoped runtime partitions. The Analyzer consumes an explicit draft or pinned release source through a shared manifest/identity library; public CI uses synthetic fixtures and private CI uses the real release. Hub data is projected from the snapshot and frames use a separate media store.

**Tech Stack:** Python 3.12 standard library, JSON Schema, existing `brief_compiler.py` and pytest/unittest suites, GitHub Actions, private R2 object storage.

**Spec:** `docs/superpowers/specs/2026-09-16-saas-canonical-publication.md`

## Global Constraints

- `release_id` is `sha256(canonical_manifest_without_release_id)` and
  `payload_digest` is the SHA-256 digest of the separate canonical runtime
  payload; canonicalization and hash versions are contract fields.
- Measured fractional runtime values use `decimal-v1` strings: normalized
  decimal text without exponent, leading zero, or trailing fractional zero
  (`215.0`/`215.00` -> `"215"`); builders never publish binary floats.
- `channel_id` is frozen at first publication, with `handle-slug-v1` or per-channel `opaque-v1`; it is never parsed or regenerated.
- Every published transcript declares `channel_id`; the loader compares declaration and partition.
- Only `assigned` mapping rows are routable; `outlier` and `analysis_group_only` remain addressable but non-routable.
- Only the publisher/builder reads the Vault after cutover; consumers require `local:<draft>` or `release:<id>`.
- The brief must be byte-identical across draft/release paths, contain no absolute path, preserve exact `wpm_source`, and pass the transcript poison test.
- Public CI uses synthetic fixtures; private Vault/release CI runs the same module against the real source and fails closed when it is unavailable.
- `/hub` uses a snapshot projection and `/hub/frame` uses an opaque media artifact ID; neither production route reads the Vault.

## Dependency order

```text
T005 snapshot manifest
├── T006 identity and loader
└── T007 source adapters and equivalence
T006 + T007 ──> T008 CI workflow wiring
T005 + T006 + T008 ──> T009 publisher and recovery
T007 + T009 ──> T010 Hub/media migration
T008 + T009 + T010 ──> T011 release hygiene and promotion
```

## Task index

### Task 1 — T005: snapshot manifest and release identity

Create `publication/manifest.py`, `publication/snapshot.schema.json`, a
versioned canonicalization-vector file, and `test_publication_manifest.py`.
Implement the separate canonical runtime payload, non-circular
`release_id_for`, strict payload/manifest byte checks, and schema checks.
Completion requires known-answer vectors plus mutation tests proving that
neither a changed manifest nor a changed payload can pass under the original
pinned release ID, including decimal normalization vectors.

### Task 2 — T006: channel identity registry and loader

Create `publication/identity.py` and `test_channel_identity.py`; add declared
`channel_id` validation to the registry loader. Completion requires collision,
interval, mixed-scheme, uniqueness, matching-partition, and mismatch tests.
Runtime-shape validation in this task also requires the resolved compilation
inputs `target_wpm`, `target_duration_s[]`, and `shot_duration_s[]`; omission or
empty measurement arrays fail closed.

### Task 3 — T007: source adapters and equivalence

Create `publication/source.py`; remove machine defaults from compiler self-check
entrypoints; compare a draft and release built from the same
`vault_commit`/`builder_version`. Completion requires byte identity, no absolute
paths, exact `wpm_source`, and the verbatim poison test.
The payload must be treated as the compiler's resolved runtime inputs, not as a
copy of the manifest or a transcript container.

### Task 4 — T008: public/private mapping CI

Add synthetic mapping fixtures and explicit regime selection, wire the public
workflow, and add the trusted Vault/release workflow using the same test module.
Completion requires a visible public PR job, a private workflow that fails
closed without an explicit release, and no real identity data in public
fixtures. It does not claim a real private execution.

### Task 5 — T009: trusted publisher and recovery

Implement the Vault builder, registry adapter, `workflow_dispatch` publisher,
identity/freshness index updates, secondary copy, and executable recovery
runbook. The publisher writes the exact canonical `manifest.json` and
`payload.json` bytes and verifies both after fetch. Completion requires
object-lock publication, authenticated approval provenance, pinned release
verification, and a clean-environment restore test.

### Task 6 — T010: Hub read-model and media store

Replace production Vault reads in `backend/main.py`/`backend/hub.py` with a
projection of the pinned snapshot and route frames through opaque media IDs.
Completion requires production configuration tests, path rejection tests, and
proof that the projection carries the snapshot release ID.

### Task 7 — T011: release hygiene and promotion

Sanitize the two versioned reports, exercise the private workflow with the
release produced by T009, verify all tests and workflow paths, and promote with
an explicit refspec. Completion requires a PR to `master`, public CI green,
private gate evidence tied to a pinned release, clean worktrees, and no
author-machine paths.

## Plan self-review

- The spec's payload, identity, lifecycle, gates, migration, and acceptance
  sections each map to at least one task above.
- The three known pre-push issues map to T008 (mapping CI) and T011 (report
  hygiene and safe push).
- T005 is the only source of canonicalization; T006 is the only source of
  identity validation; T008 is the only CI regime wiring; T009 is the only
  publisher/registry writer.
- T008 can complete with workflow wiring and synthetic CI only; T011 owns the
  first real private-gate execution after T009 produces a pinned release.
- No task uses a silent skip, a machine default, a second mapping copy, or an
  automatic clustering heuristic.
