# Wayfinder — Vault to canonical publication

## Destination

Produce a buildable specification for a versioned publication boundary between
the Obsidian Vault and the Analyzer: the Analyzer and CI can consume formulas,
approved sub-formula mappings, FORMAT CARD provenance, and channel isolation
without requiring a developer's local `VAULT_DIR`. The destination is a
contract and migration route, not the SaaS implementation itself.

## Notes

- T001–T005 harden the current pre-SaaS workflow; T005's fail-closed
  `VAULT_DIR` gate remains valid until this boundary exists.
- This Wayfinder map and its child decision tickets are versioned planning
  artifacts in the Analyzer repository.
- The Vault is currently the local canonical source. No SaaS runtime boundary
  has been adopted yet.
- Deterministic, human-approved mapping remains authoritative; automatic
  clustering is out of scope.
- Keep project and channel identity distinct even when visual style or other
  FORMAT CARD values happen to be shared.
- Use domain-modeling and codebase-design vocabulary when resolving decisions;
  hand off to `to-spec`, then `to-tickets`, once the route is clear.
- Draft specification: [SaaS Canonical Publication Boundary](../../docs/superpowers/specs/2026-09-16-saas-canonical-publication.md), pending adversarial review before `to-tickets`.

## Decisions so far

- [T005 — Harden the release gate and reconcile documentation](../deterministic-subformula-mapping/issues/005-release-gate-and-documentation.md): the current local gate fails closed when the canonical Vault mapping cannot be verified; it is a pre-SaaS safety gate, not the target runtime architecture.
- [Decide the canonical publication boundary](issues/01-canonical-publication-boundary.md): publish one self-contained project snapshot, consume channel partitions by immutable identity, and embed versioned runtime taxonomy/provenance instead of relying on `VAULT_DIR`.
- [Decide publication lifecycle and versioning](issues/02-publication-lifecycle-and-versioning.md): a Vault-approved revision is manually published by trusted CI to private immutable R2, consumed by pinned release ID, with separate public-synthetic and private-real verification regimes and exercised recovery.
- [Decide Analyzer and CI consumption](issues/03-analyzer-and-ci-consumption.md): consumers use mandatory opaque source handles and pinned releases; public/private tests share one module; brief output is byte-identical, and the remaining hub/frames migration uses a separate media artifact store.
- [Decide channel identity and handle history](issues/04-channel-identity-and-handle-history.md): channel IDs are frozen at first publication, handle history is human-approved and interval-based, cross-release uniqueness lives in an audited identity index, and storage is keyed by channel ID rather than the current handle.

## Not yet specified

- How the builder, snapshot registry, synthetic mapping fixtures, and hub/media
  artifact migration are implemented and sliced.
- The SaaS tenancy, authorization, and lifecycle model; revisit after the
  publication boundary is defined.

## Out of scope

- Implementing SaaS endpoints, cloud infrastructure, authentication, or a
  production migration.
- Rewriting FORMAT CARDs or transcripts, changing the canonical `Realism`
  scale, or inventing automatic clustering.
- Resolving `dark_psycho`, Stickman dates, voice calibration, or engine
  validation.
