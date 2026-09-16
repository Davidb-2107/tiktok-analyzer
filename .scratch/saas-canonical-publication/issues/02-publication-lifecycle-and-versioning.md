# Decide publication lifecycle and versioning

Status: resolved
Type: grilling
Blocked by: none (01 resolved)

## Question

How does an approved Vault state become a published canonical snapshot, and how
are validation, ownership, versioning, rollback, and provenance enforced?

The decision must define the publisher, required gates, immutable versus mutable
records, handling of rejected or incomplete source data, and how a release can
be reproduced without access to the author's local Vault path.

The publication gate must carry the resolved taxonomy semantic version together
with the digest of the authoritative taxonomy module. Matching value arrays
alone are insufficient because the Vault and CI modules can have different
behavior.

The decision must also define the version rule: the taxonomy version is a
monotone semantic version owned by the taxonomy authority, it is bumped for
any allowed-value or validation-behavior change, and every published snapshot
stores the authoritative module digest alongside it. The digest is the
behavioral anchor; the version is the human-readable compatibility signal.

## Comments

### Round 1 — working consensus

- Publication is human-triggered but CI-executed. The human approves an
  immutable `vault_commit`; the builder must reproduce the snapshot from that
  revision. The publisher belongs with the Vault, which owns the source data,
  not with the Analyzer consumer.
- The release registry must record approver, approval time, `vault_commit`,
  builder identity/version, release digest, and any movement of the mutable
  `current` alias.
- A release is an immutable snapshot whose content address is derived from a
  canonical serialization of its manifest. The readable release label is
  separate from that content address. A consumer must be able to recalculate
  the digest and verify taxonomy/module digests offline.
- `current` is a separate mutable pointer with its own audit trail; it never
  changes an existing snapshot. The manifest pins `builder_version` because
  the same Vault revision can resolve differently under different builders.
- Publication categories are explicit: blocking validation failures prevent a
  snapshot; `assigned`/`analysis_group_only`/`outlier` records may be present
  but only `assigned` records are routable; typed informational data may be
  published without becoming runtime input. Staleness is recorded, not an
  automatic publication failure.
- The unresolved business decision is who may read published snapshots and
  their embedded formulas, cards, and mappings. Publication visibility must
  not be inferred from the public Analyzer repository.

### Round 2 — visibility and verification regimes

- The public/private boundary is ratified rather than invented: real snapshots
  containing formulas, cards, mappings, and real provenance stay private;
  public Analyzer fixtures remain synthetic and contain no real handles, video
  IDs, or canonical mapping-note references.
- Real digests and release metadata remain inside the private snapshot/manifest.
  The public repository may publish the manifest schema, but not values that
  reveal private release cadence or require credentials unavailable to forked
  pull requests.
- There are two explicit verification regimes: trusted private CI runs the
  real snapshot gate; public CI runs fail-closed synthetic fixtures. Public CI
  must not claim to validate the private production snapshot.
- Taxonomy values and structural support files already present in public
  fixtures are treated as publishable structure, not private business assets.
- Public CI needs a mechanical fixture denylist for real handles, real mapped
  video IDs, and the canonical mapping-note path, so the synthetic-fixture
  boundary cannot depend on author discipline alone.

### Round 3 — trusted publisher and registry

- The publisher is a Vault-side `workflow_dispatch` workflow, following the
  existing privileged-provider-smoke pattern. It approves and builds from an
  immutable `vault_commit`; ordinary Vault pushes never publish automatically.
- The snapshot is stored in a private R2-backed registry using native
  write-once/object-lock or an equivalent immutable primitive. A private Vault
  branch is rejected because it grants repository-wide access and couples the
  consumer to Vault layout; encrypted blobs in the public Analyzer repository
  are rejected because they make the public repo an asset-distribution
  channel.
- Consumer credentials are read-only and scoped to the required artifact, are
  absent from public CI, and the runtime receives the snapshot through an
  injected URI/path context rather than discovering paths from environment
  variables. Production consumers pin a `release_id`; they never use `latest`
  or `current` as a runtime input.
- After fetch, the consumer recomputes the content hash and compares it with
  the manifest, failing closed on any mismatch. `VAULT_DIR` is authoring-only
  and explicitly non-production.
- The remaining lifecycle decision is retention, backup, and restoration once
  the registry becomes the runtime source of truth.

### Round 4 — retention and recovery

- Retain every immutable snapshot while the payload remains strictly textual;
  if binaries are ever admitted, reopen the retention policy rather than
  silently extending this rule. Pruning is rejected because it makes pinned
  releases expire and breaks immutability.
- The Vault is an input, not a backup: reconstruction can vary with
  `vault_commit`, `builder_version`, taxonomy-module digest, and SOT versions.
- The recovery runbook is an executable control: fetch the secondary copy,
  recompute and compare the manifest/content hash, run consumer validation,
  compile a brief in a clean environment, and compare it to a recorded
  expected output. A failed step fails the exercise.
- Record RPO/RTO, keep the secondary copy in a distinct failure domain, verify
  it by hash, and retain the approval/audit manifest even if payload retention
  changes later.
- `brief_compiler.py` currently stores transcript verbatim in registry records,
  but no downstream compiler path consumes that field. Whether verbatim
  third-party text belongs in a published immutable snapshot is therefore a
  separate retention/rights decision from retaining formulas, cards, mappings,
  and provenance.

## Answer

T02 resolves the publication lifecycle as follows.

- A Vault-side `workflow_dispatch` publisher builds from a human-approved,
  immutable `vault_commit`. Ordinary Vault pushes and Analyzer merges never
  publish automatically. The release registry records the approver, approval
  time, source revision, builder identity/version, release digest, and alias
  movements.
- The builder emits a self-contained immutable snapshot to a private R2-backed
  registry using native write-once/object-lock semantics. Its content address
  is derived from the canonical manifest serialization; a readable release
  label is separate. The manifest includes `builder_version`, taxonomy
  semantic version plus authoritative-module digest, SOT versions/digests,
  and per-artifact digests. Consumers verify these offline after fetch.
- `current` is only a human-facing mutable pointer with its own audit trail.
  Runtime consumers pin a `release_id`, never `latest` or `current`, and fail
  closed if the fetched content hash disagrees with the manifest. `VAULT_DIR`
  is authoring-only and non-production.
- Blocking validation failures prevent publication. Explicit
  `assigned`/`analysis_group_only`/`outlier` statuses remain in the snapshot,
  but only `assigned` records are routable. Typed informational data may be
  published without becoming runtime input; staleness is recorded rather than
  silently refreshed or treated as a publication failure.
- Real formulas, cards, mappings, and private provenance stay in the private
  registry. Trusted private CI or a Vault pre-push hook owns the real-identity
  leak scan; the public CI must not contain real handles, video IDs, or
  canonical mapping-note paths in a denylist. Public CI only validates the
  synthetic-fixture contract. Taxonomy structure already public in fixtures is
  not treated as a private business asset.
- All snapshots are retained while payloads remain strictly textual, with a
  hash-verified secondary copy in a distinct failure domain. The recovery
  runbook is an exercised control: fetch, hash-check, validate fail-closed,
  compile in a clean environment, and compare against recorded expected
  output. It records RPO/RTO and preserves the approval/audit manifest.
  Introducing binary payloads reopens the retention decision.
- The published payload is defined by compiler inputs, not by every field
  loaded from the source registry. Transcript verbatim is excluded from the
  runtime snapshot because the current compiler and output schema do not
  consume it; the Vault owns its separate retention/rights policy. Backend
  transcript display remains a backend concern, not a snapshot dependency.

The local-to-published equivalence suite must poison the source transcript and
assert byte-identical output. If that test ever changes, the payload boundary
must be explicitly revisited rather than silently becoming incomplete.

The approver identity is sourced from the authenticated GitHub Actions actor
(`github.actor_id` plus `github.actor`) attached to the manual workflow run;
it is never a free-form manifest field.
