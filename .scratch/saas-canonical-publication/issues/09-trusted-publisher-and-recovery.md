# T009 — Publish immutable snapshots and exercise recovery

Status: open
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
context, then produces the manifest/payload pair required by T005. The
registry adapter writes a pinned `release_id`, the identity index, the
build-time freshness result, and the secondary copy.

## Acceptance criteria

- Ordinary Vault pushes never publish snapshots; only the manually dispatched
  trusted workflow can write the registry.
- The manifest records `vault_commit`, `builder_version`, taxonomy/module and
  SOT digests, voice-profile digest, build-time freshness, and
  `github.actor_id`/`github.actor` as approval provenance.
- R2 write-once/object-lock prevents replacement of an existing release ID.
- `current` is an audited alias to a pinned release and is never consumed as
  the runtime source.
- The identity index persists across releases, is auditable, and can be
  reconstructed from retained snapshot provenance.
- All text-only snapshots are retained; frames are excluded from this store.
- The runbook restores a clean environment, verifies manifest and payload
  hashes, validates, compiles, compares expected output, and records measured
  RPO/RTO for the secondary copy.

## Out of scope

SaaS tenancy, billing, customer authorization, and frontend changes are not
part of the publisher.
