# Decide channel identity and handle history

Status: resolved
Type: grilling
Blocked by: none (01 resolved)

## Question

How is the durable `channel_id` issued at publication, and how does it relate
to mutable channel handles over time?

The decision must define whether the ID is a slug or opaque value, who assigns
it, its collision scope, when it becomes immutable, how handle renames and
historical provenance are represented, and how existing sub-formula IDs,
channel-scoped artifact names, and `(project_id, channel_id, subformula_id)`
uniqueness behave during migration. A handle-derived ID may be convenient at
creation, but a later rename must not change identity or published references.

## Comments

### Round 1 — working consensus

- For existing channels, `channel_id` is the current canonical handle slug
  (`handle[1:]`) at first publication and is then frozen. This ratifies the
  current directory/formula layout with no correspondence table for the
  initial migration.
- The slug is an opaque identifier after assignment. It must never be parsed
  for semantic meaning and must not be regenerated from a later handle.
- Uniqueness is scoped as follows: `project_id` is globally identified by its
  declared scheme; `channel_id` is unique within `project_id`;
  `subformula_id` is unique within `(project_id, channel_id)`; platform
  `video_id` is globally unique, while assignment is scoped to
  `(project_id, channel_id, video_id)`; artifact names derive verbatim from
  `(project_id, channel_id, subformula_id)`.
- A handle rename preserves `channel_id` only when human-approved continuity
  evidence exists. Handle history is interval-based
  `(handle, valid_from, valid_to, channel_id, evidence, declared_by)`; lookup
  by handle must be time-bounded because platforms can recycle handles.
- Existing handle-prefixed sub-formula IDs remain immutable historical IDs and
  are never parsed. Existing cards/transcripts retain their historical handle
  text but resolve through `channel_id`.
- `_slug()` is not an identity or artifact-name function: it normalizes and
  truncates punctuation, so stable artifact names use the frozen `channel_id`
  verbatim.
- The loader migration must stop validating a directory name against the
  current handle. Storage is keyed by the frozen `channel_id`, while the
  current handle is a frontmatter/history attribute.

### Round 2 — resolved constraints

- The publisher assigns `channel_id = handle[1:]` for an existing channel at
  its first publication, then freezes it. If that value is already allocated
  in the same `project_id` (for example after handle recycling), publication
  does not block indefinitely: it allocates a fresh opaque ID and records
  `channel_id_scheme: opaque-v1`. The handle-derived scheme remains
  `handle-slug-v1`; no consumer parses either scheme.
- Allocation is checked against a persistent, mutable, audited identity index
  that survives releases. The index records the channel ID, origin handle,
  origin release, authenticated actor, scheme, and the handle intervals. The
  publisher carries the resulting identity into each immutable snapshot; a
  snapshot alone is not the authority for cross-release uniqueness.
- The published channel record contains `channel_id`, `channel_id_scheme`,
  `current_handle`, and `handle_history`. `current_handle` is a convenience
  projection of the open history interval, and the publisher rejects any
  disagreement between them. History entries contain `handle`, `valid_from`,
  `valid_to`, `evidence`, `declared_by`, and `declared_at`; the dates are UTC,
  `valid_to` is null for the current interval, and each bound carries an
  exact/approximate precision marker rather than an invented exact date.
  `channel_id_scheme` belongs to this channel record, not to the project, so a
  project may contain both handle-derived and opaque channel IDs.
- A rename preserves a channel ID only after an authenticated human
  declaration in the Vault, with evidence and non-overlapping intervals.
  The publisher rejects both overlapping intervals for one channel and
  overlapping intervals for one handle across different channel IDs. Without
  approved continuity evidence, the renamed source is a new channel and uses
  the collision rule above.
- The identity declaration lives in the Vault as authoring authority; the
  publisher validates and resolves it into the snapshot. Cards and transcripts
  are assigned to the `channel_id` partition, while historical handle text is
  retained as provenance. Existing handle-prefixed `subformula_id` values are
  immutable opaque historical IDs and are never parsed or rewritten.
- Existing directories need no physical move when their current slug becomes
  the frozen channel ID. The loader changes its safety check to compare the
  record's `channel_id` with the partition directory, not the current handle;
  a matching ID with an old handle loads, while an ID/partition mismatch
  fails. This regression must be tested in both directions.

## Answer

`channel_id` is issued by the publisher at first publication: existing
channels retain their current `handle[1:]` value as `handle-slug-v1`, frozen
thereafter. Handle recycling is handled through the persistent audited
identity index; a collision receives an opaque `channel_id` under
`opaque-v1`, rather than silently reusing an identity or blocking publication.

The identity index is the cross-release authority. The Vault holds the human
continuity declaration and evidence; the publisher validates it, records the
authenticated actor and release, and embeds the resolved channel record in
each snapshot. Consumers use the explicit `channel_id` and never derive it
from a current handle. The `channel_id_scheme` is scoped to that channel
record, not to the project, allowing mixed schemes within one project.

Handle history is interval-based in UTC, with explicit precision for
approximate boundaries, `valid_to: null` for the current interval, and two
non-overlap invariants: intervals cannot overlap within one channel, nor for
one handle across different channel IDs. `current_handle` is validated as the
projection of the open interval.

The storage migration is therefore minimal: existing slug directories remain
in place, but the loader's coherence check is keyed to the frozen
`channel_id`. Old handles and old handle-prefixed subformula IDs remain
historical provenance; they are not rewritten or parsed. A record whose
channel ID disagrees with its partition is rejected, and a record using an
old handle with the correct frozen channel ID remains valid.
