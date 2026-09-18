# T009 — Publish immutable snapshots and exercise recovery

Status: resolved
Type: implementation
Repository: Vault repository
Blocked by: T005, T006, T008

## Goal

Build approved Vault revisions into immutable private R2 snapshots, record
authenticated publication provenance, maintain the identity/freshness indexes,
and prove restoration from a secondary copy.

## Files

- Create `Projects/Sourcing/tools/publication_builder.py`.
- Create `Projects/Sourcing/tools/publication_registry.py`.
- Create `Projects/Sourcing/tools/tests/test_publication_builder.py`.
- Create `.github/workflows/publish-snapshot.yml` with `workflow_dispatch`
  only.
- Create `docs/runbooks/snapshot-recovery.md`.

## Interfaces

The builder consumes an explicit `vault_commit` and authenticated dispatch
context, then produces the exact canonical `manifest.json`/`payload.json`
pair required by T005. The
registry adapter writes a pinned `release_id`, the identity index, the
build-time freshness result, and the secondary copy.

Before building any release, T009 requires the one-time T012 migration to have
added explicit `channel_id` declarations to every legacy transcript and
formula in the selected Vault release scope. It must fail closed if any
record is still missing the declaration.

## Acceptance criteria

- Ordinary Vault pushes never publish snapshots; only the manually dispatched
  trusted workflow can write the registry.
- The manifest records `vault_commit`, `builder_version`, taxonomy/module and
  SOT digests under the T005 field names, voice-profile digest, build-time freshness, and
  `github.actor_id`/`github.actor` as approval provenance.
- The registry stores the exact canonical manifest and payload bytes and
  verifies them after fetch; it never parses and reserializes a release.
- R2 write-once/object-lock prevents replacement of an existing release ID.
- `current` is an audited alias to a pinned release and is never consumed as
  the runtime source.
- The identity index persists across releases, is auditable, and can be
  reconstructed from retained snapshot provenance.
- All text-only snapshots are retained; frames are excluded from this store.
- The runbook restores a clean environment, verifies manifest and payload
  hashes, validates, compiles, compares expected output, and records measured
  RPO/RTO for the secondary copy.

## Resolution

The recovery drill was executed on 2026-09-18 against disposable VPS staging
using the pinned R2 release
`sha256:262e90930dbae113339a5933d0f905294ba1ec9b5bdb3ee82dd1857663ddd939`.
The verifier passed for both materialized copies. The manifest and payload
SHA-256 values were respectively
`986df408c898fc458a79e5bf88268cbe36aedb0c3a1a0e2aae72002f7e4b2172` and
`89e0fcb69680230199430141a2d6080f8cd06ab6f7913a6e0b5f72264cec57b5`.
All three assigned formulas were compiled from the clean secondary restore
with explicit channel/subformula selectors, and each output matched the
expected output byte-for-byte. Measured RPO was approximately zero seconds;
measured RTO from clean-directory creation through successful comparisons was
0.586 seconds. The production release and running container were not changed.

## Out of scope

SaaS tenancy, billing, customer authorization, and frontend changes are not
part of the publisher.
