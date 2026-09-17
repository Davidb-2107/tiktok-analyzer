# Decide the canonical publication boundary

Status: resolved
Type: grilling
Blocked by: none

## Question

What exactly is the canonical published artifact between the Obsidian Vault and
the Analyzer, and which data and identity guarantees must it carry?

The decision must cover the minimum unit of publication, project and channel
identity, formulas and approved sub-formula mappings, FORMAT CARD/transcript
provenance, schema/version identity, and what remains editable-only in the
Vault. It must state how a consumer can distinguish two channels in one
project even when their visual style or taxonomy values overlap.

## Comments

### Round 1 — working consensus

- Publication atomicity is a project-level snapshot; consumption is a
  channel-scoped partition. The approved mapping remains one shared project
  document, so publication must not duplicate it per channel.
- The snapshot must be self-sufficient for compilation. Vault pointers alone
  are not an acceptable runtime contract because they recreate `VAULT_DIR`.
- The runtime boundary must include the formula, FORMAT CARD-derived fields,
  transcript/card provenance, approved mapping assignments, SOT inputs needed
  by compilation, and version/digest metadata. Raw media and editable Vault
  prose are not required in the runtime payload.
- The approved Markdown mapping remains the human-editable source, but the
  published boundary should contain a structured mapping representation with
  typed channel, video, sub-formula, and status fields.
- Channel identity is not the mutable TikTok handle. Use an immutable internal
  `channel_id`; retain the normalized `@handle` for matching and historical
  provenance. Resolve explicitly whether the existing `niche` is the project
  identifier or must be replaced by a distinct stable `project_id`.
- The published snapshot must pin the taxonomy version used for validation and
  include a manifest with project identity, schema version, source revision,
  and per-artifact digests.
- Acceptance should prove that compiling from the local Vault and from the
  published snapshot produces identical JSON apart from explicitly volatile
  fields.

### Round 2 — working consensus

- For this boundary, `project_id` explicitly means the Analyzer's `niche`
  scope, not the Vault's `Projects/TikTok/<Name>` directory. The published
  identifier is opaque and non-parsed; the manifest records
  `project_id_scheme: "niche"`.
- The snapshot separates `runtime` data from `provenance` metadata. Runtime
  carries resolved duration values, allowed taxonomy values, validated engine
  facts, calibrated voice values, formulas, cards, and structured mapping
  records. Provenance carries source revisions, SOT versions, and digests; no
  runtime decision follows a local path or audit-only field.
- Duration, taxonomy, engine facts, and voice data are pinned at publication;
  the consumer must be able to detect that a snapshot is stale rather than
  silently refreshing it.
- Existing `subformula_id` values are opaque immutable identifiers. Their
  handle-like prefix is historical and must never be parsed. Assignment
  uniqueness is scoped to `(project_id, channel_id, subformula_id)`.
- `channel_id` is the durable identity; the normalized handle is matching and
  provenance data. Stable artifact naming based on `channel_id` is a constraint
  for the Analyzer/CI consumption decision.
- The remaining boundary question is the single authority and versioning
  contract for the taxonomy; its resolved values must be embedded in each
  snapshot even if the source is external to the Vault.

### Round 3 — corrected taxonomy decision

- The Analyzer does not define the taxonomy. The current runtime authority is
  `Projects/Sourcing/tools/format_card_registry.py` in the Vault; the Analyzer
  imports that module through `VAULT_DIR` and fails if it is absent.
- The Vault module's docstring claim that the canonical taxonomy lives in
  `brief_compiler.py` is incorrect and must be corrected as follow-up work.
- The published snapshot, not a local Vault path, is the runtime boundary. It
  must embed `taxonomy: {version, styles, mechanics, realism_values}` and
  validate that payload at load time.
- The current `project_id == niche` decision remains, with an explicit opaque
  `project_id_scheme: "niche"`; the Vault folder name is not published
  identity.
- A shared taxonomy package is deferred. Until then, the Vault and CI copies
  must be generated or digest-checked rather than maintained as manual forks.
  The current fixture copy is known to differ in module behavior despite
  matching taxonomy values, so this is a release constraint, not optional
  cleanup.

## Answer

The publication boundary is an immutable, project-level snapshot. Its
consumption interface is partitioned by channel, but the shared approved
mapping remains one project artifact and is never duplicated per channel.

For this migration, `project_id` is explicitly the Analyzer `niche` scope and
is recorded with `project_id_scheme: "niche"`; the Vault folder name is not
published identity. Channel identity is an immutable `channel_id`, while the
normalized `@handle` is matching/provenance data. Existing `subformula_id`
values are opaque immutable IDs: their handle-like prefixes are historical and
must never be parsed. Assignment uniqueness is
`(project_id, channel_id, subformula_id)`.

The snapshot is self-sufficient for compilation and contains a `runtime`
section with resolved formulas, cards, structured mapping records, duration
values, validated engine facts, calibrated voice values, and the taxonomy
values used for validation. A separate `provenance` section carries source
revisions, SOT versions, taxonomy version, and per-artifact digests. It must
not contain runtime dependencies on `VAULT_DIR`, local paths, or executable
source files. Published snapshots are pinned and must report staleness rather
than silently refreshing.

The current taxonomy authority is the Vault module
`Projects/Sourcing/tools/format_card_registry.py`; the Analyzer currently has
no taxonomy definition and imports that module through `VAULT_DIR`. Its
docstring's claim that the source is in `brief_compiler.py` is false and must
be corrected in follow-up work. The snapshot embeds
`taxonomy: {version, styles[], mechanics[], realism_values[]}` plus the digest
of the authoritative taxonomy module, so equal value arrays cannot mask module
behavior drift. A shared taxonomy package is deferred; until then, Vault and CI
copies must be generated or verified by digest, not manually forked. The local
and published paths must eventually produce identical brief JSON except for a
named, finite list of explicitly volatile fields.

Deferred to the publication and consumption decisions: how `channel_id` is
issued and retained, how snapshots are published/versioned/rolled back, and
how stable channel-scoped artifact names replace handle-derived local paths.
