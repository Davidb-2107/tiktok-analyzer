# SaaS Canonical Publication Boundary

Status: approved for implementation on 2026-09-16.

This specification turns the resolved decisions in
`.scratch/saas-canonical-publication/issues/01-*.md` through `04-*.md` into
one implementation contract. It defines the Vault-to-snapshot boundary; it
does not implement SaaS endpoints or cloud infrastructure.

## Goal

Publish one reproducible project snapshot from the private Vault so that the
Analyzer, backend, workers, and CI consume an explicit snapshot or published
read-model instead of reading a developer's Vault. A project may contain
several independently identified channels, and a channel may contain several
human-approved sub-formulas.

## Vocabulary and authority

- **Project snapshot**: the immutable, versioned publication unit. Its
  `project_id` is the source niche identifier under an explicit
  `project_id_scheme`; the identifier is opaque to consumers.
- **Channel partition**: the records selected by one immutable `channel_id`.
  Channel identity is independent of visual style, `Realism`, hooks, or any
  other FORMAT CARD value.
- **Publisher**: the only post-cutover actor allowed to read the Vault and
  build a snapshot. It runs in trusted, manually dispatched Vault CI.
- **Consumer**: the Analyzer, backend, worker, or CI process that receives a
  required source context and reads a snapshot or published read-model.
- **Canonical mapping**: the human-approved video-to-sub-formula mapping.
  Code applies it; code does not discover or infer it.

The Vault remains the authoring authority for formulas, cards, identity
declarations, and approved mappings. The immutable snapshot is the runtime
authority for a pinned release. The cross-release identity index and current
freshness index are mutable, audited registries outside the snapshot.

## Snapshot contract

The snapshot is one project-level object with channel-scoped records. The
mapping is stored once at project level and is referenced by channel and video
scope; it is not duplicated into separate per-channel copies.

```text
snapshot
├── project_id
├── project_id_scheme
├── release_id
├── runtime
│   ├── taxonomy
│   ├── channels[]
│   ├── formulas[]
│   ├── cards[]
│   ├── mappings[]
│   └── resolved compilation inputs
└── provenance
    ├── vault_commit
    ├── builder_version
    ├── taxonomy module digest
    ├── channel identity history[]
    ├── SOT versions and digests
    ├── voice-profile digest
    └── build-time freshness results
```

The exact serialization may evolve, but every implementation must preserve
these boundaries:

- `runtime` contains only inputs consumed by compilation and the resolved
  values needed by consumers. A runtime channel record contains
  `channel_id`, `channel_id_scheme`, and `current_handle`; identity evidence,
  interval precision, and declaration metadata live under provenance.
- `provenance` explains which approved source and builder produced the
  runtime data. Provenance is not a second runtime source of truth.
- The payload excludes transcript verbatim, raw media, editable Vault prose,
  and other fields not consumed by the compilation path. The Vault retains
  those authoring/backend artifacts under their own policy.
- `script.wpm_source` is retained as the exact resolved string because it
  contains non-reconstructible corpus provenance. The manifest additionally
  carries the voice-profile digest.
- Runtime taxonomy is embedded as
  `{version, styles[], mechanics[], realism_values[]}`. `version` is the
  monotone semantic compatibility version owned by the taxonomy authority and
  is bumped for allowed-value or validation-behaviour changes. The digest of
  the authoritative taxonomy module is stored beside it because equal value
  arrays do not prove equal module behaviour.

The channel record is therefore represented across the two namespaces without
duplicating authority: runtime carries the identity needed for compilation and
routing, while provenance carries the evidence and historical explanation.

## Identity contract

### Project and channel identity

- `project_id` equals the current niche identifier for this migration, is
  opaque to consumers, and is interpreted only under `project_id_scheme`.
- For an existing channel, the publisher assigns
  `channel_id = handle[1:]` at first publication under
  `channel_id_scheme: handle-slug-v1`, then freezes it.
- `channel_id` is unique within `project_id`; it is never regenerated from a
  later handle and is never parsed for meaning.
- If the first handle-derived value is already allocated in the same project,
  the publisher allocates a fresh opaque ID under
  `channel_id_scheme: opaque-v1`. Publication must not silently reuse an old
  identity or block forever.
- `channel_id_scheme` belongs to the channel record, not the project record.
  A project may therefore contain both schemes.
- Artifact names and storage keys use the frozen `channel_id` verbatim. The
  lossy presentation helper `_slug()` is not an identity or artifact naming
  function.
- `subformula_id` is unique within `(project_id, channel_id)` and remains
  opaque. A platform `video_id` is globally identified within its platform,
  while its assignment is scoped to `(project_id, channel_id, video_id)`.
  Artifact identity is derived from
  `(project_id, channel_id, subformula_id)` without parsing any component.

### Channel record and handle history

Every published channel identity is represented across the runtime and
provenance namespaces:

```text
runtime:
channel_id
channel_id_scheme
current_handle

provenance:
handle_history[]
```

Each history entry contains:

```text
handle
valid_from
valid_to
valid_from_precision
valid_to_precision
evidence
declared_by
declared_at
```

Dates are UTC. `valid_to: null` means the current interval. When a boundary
cannot be known exactly, the record carries an `approximate` precision marker;
it does not invent an exact date. `current_handle` is a convenience
projection of the open history interval and the publisher rejects any
disagreement between the two.

The following invariants are mandatory:

1. Intervals for one `channel_id` never overlap.
2. Intervals for one handle belonging to different `channel_id` values never
   overlap.
3. A rename keeps the same `channel_id` only when an authenticated human has
   declared continuity in the Vault with evidence. Otherwise it is a new
   channel and follows the collision rule.
4. The identity index records the allocation, origin handle, origin release,
   scheme, actor, evidence, and intervals and survives release rotation. A
   snapshot alone cannot prove cross-release uniqueness.

Cards and transcripts declare `channel_id` in their frontmatter and the
publisher rejects a declaration that disagrees with the partition. During the
one-time migration, the trusted builder may populate this field from the
verified legacy partition and write it into the published representation; the
runtime loader never silently inherits identity from a directory. Historical
handle text remains provenance. Existing handle-prefixed `subformula_id`
values remain opaque historical IDs: they are neither rewritten nor parsed.

The identity index is a mutable audited allocation cache, not an irreplaceable
source of truth: it is reconstructible from retained snapshot provenance.
Restoration tooling must be able to rebuild it and then re-run the uniqueness
invariants before accepting new publication.

## Publication lifecycle

1. A human approves a Vault revision identified by `vault_commit`. The
   approval provenance comes from the authenticated GitHub dispatch actor
   (`github.actor_id` and `github.actor`), never from a free-form manifest
   field.
2. A trusted Vault workflow is started through `workflow_dispatch`; ordinary
   Vault pushes never publish runtime data.
3. The publisher validates identity declarations, source completeness,
   mappings, taxonomy, SOT inputs, and all integrity gates.
4. The builder creates a canonical snapshot and manifest containing the
   `builder_version`, source revisions, digests, taxonomy information, voice
   profile digest, and build-time freshness results.
5. The snapshot is written to a private immutable R2 registry using its native
   write-once/object-lock primitive. `release_id` is the content address of
   the release: `sha256(canonical_manifest_without_release_id)`, with the
   algorithm and canonicalization version fixed by the manifest contract. The
   manifest includes the payload digest. A consumer fetches the pinned
   `release_id`, recomputes the manifest address without trusting the
   manifest's own ID field, compares it to the pinned ID, and then verifies
   the payload digest. This is the non-circular trust root.
6. Consumers pin a `release_id`; they never use `latest` or `current` as a
   runtime dependency. `current` is only an audited human-facing alias that
   resolves to a release ID; it is never accepted as the runtime pin.

All text-only snapshots are retained. If binary payloads are admitted, this
retention decision is reopened. Frames therefore use a separate media artifact
store and policy; they never enter the text snapshot.

The recovery runbook is an executable control: restore into a clean
environment, fetch the pinned release, recalculate and compare hashes,
validate the snapshot, compile a brief, and compare it with an expected
recorded output. The secondary copy lives in a distinct failure domain and is
hash-verified. The policy records `RPO ≈ 0` when the secondary copy is made at
publication and an `RTO` equal to the measured restoration time.

## Gates and status semantics

The publisher and consumer preserve three distinct outcomes:

- **Blocking**: malformed context, missing required source, schema failure,
  hash mismatch, publisher-detected taxonomy/module-digest failure, identity
  collision or interval overlap, invalid channel partition, or malformed
  mapping. The operation fails closed.
- **Publishable but non-routable**: a valid mapping with status `outlier` or
  `analysis_group_only`. It remains addressable and auditable but cannot be
  selected as a production formula.
- **Informative**: a valid snapshot whose immutable manifest reports
  build-time freshness as `stale`, or a current-freshness observation from the
  separate audited index. The consumer does not infer freshness against an
  authority it cannot access; a caller decides whether an informative result
  is acceptable for production.

Only `assigned` mapping rows are routable. A consumer never promotes an
outlier or analysis-only group and never infers a formula from style, Realism,
hook frequency, or another majority heuristic.

Integrity and freshness are separate:

| Check | Owner | Failure/result |
| --- | --- | --- |
| Payload hash, manifest hash, schema, internal cross-record consistency | Consumer | Fail closed on invalid data |
| Supported compatibility range | Consumer | Fail closed when unsupported |
| Current SOT/taxonomy freshness and authoritative-module digest | Publisher/private CI | Recorded in the immutable manifest at build time |
| Current freshness of already-published releases | Private audited freshness index | Mutable observation; never rewrites the snapshot |

The consumer cannot infer currentness without the current authorities. A
valid but older snapshot may load with a machine-readable stale signal and no
automatic refresh; a caller may separately reject it for production while
preserving reproducibility.

## Migration contract

### Source context

Consumers require an explicit opaque source context such as
`local:<path>` for a locally built draft or `release:<id>` for a published
snapshot. Missing or malformed context fails explicitly. Author-machine
defaults are forbidden.

Local development compiles from a draft produced by the same builder as the
published path. `VAULT_DIR` exists only inside that builder (and, temporarily,
the local equivalence harness); it is not a runtime discovery mechanism.

### Analyzer and loader

The loader is re-indexed on frozen `channel_id`, not on the current handle.
Existing directories need no physical move when their current slug is the
frozen channel ID. After migration:

- a record with an old handle and a declared `channel_id` matching its
  partition loads;
- a record whose declared `channel_id` disagrees with its partition fails
  closed;
- current handles are read as history attributes, never used as identity;
- the loader preserves the channel-scoped mapping and does not duplicate it.

### Hub and frames

The backend `/hub` surface consumes a deterministic read-model projection of
the pinned snapshot's `runtime`; it is not a second publication artifact. It
may be materialized or cached, but it inherits the snapshot's `release_id`,
retention, and audit trail. It does not mount or discover the Vault in a
production profile. `/hub/frame` resolves an opaque `frame_id` from a
separate media artifact store; callers never provide filesystem paths.
Exposure is controlled by build/configuration profile, not by an incidental
runtime `is_dir()` check.

## Verification and acceptance

The public and private regimes use one parameterized test module, not forked
test files:

- Public CI runs synthetic fixtures only. It validates the schema, routing,
  identity invariants, and the synthetic mapping contract. It contains no
  real handles, video IDs, or canonical mapping-note paths.
- Trusted private CI runs the same module against the approved real snapshot
  from the Vault/release CI boundary, not from public Analyzer pull-request
  jobs. It checks out the Analyzer revision under test and supplies an
  authenticated pinned release. Missing private source is a test error, never
  a skip. The private regime owns real-identity leak scanning and the
  canonical real-ID assertions; those real-only assertions are not copied
  into public fixtures.

The module receives an explicit regime/source configuration. Public runs
select synthetic contract cases; private runs select the required real-source
cases. The same test code is parameterized for both paths, and the private
canonical gate is fail-closed rather than guarded by `skipUnless`.

The feature is accepted only when all of the following are demonstrated:

1. A local draft and a published release are built from the same
   `vault_commit` and `builder_version`, then compiled through
   `local:<draft>` and `release:<release_id>` source paths. Their brief JSON
   is byte-identical.
2. No absolute filesystem path occurs anywhere in the brief output.
3. Replacing transcript verbatim with a poison sentinel leaves the brief
   byte-identical; if this fails, transcript data has become a compilation
   input and the payload decision must be reopened.
4. The exact `wpm_source` string is preserved.
5. Every published transcript declares `channel_id`; the shared tests cover
   both channel partition directions: an old handle with the declared frozen
   ID loads, and a tampered declared ID/partition mismatch fails.
6. Mapping rows with `assigned`, `analysis_group_only`, and `outlier` preserve
   their statuses, with only `assigned` routable.
7. Public synthetic and private real runs execute the same test module, with
   no silently skipped canonical gate in the private regime.
8. The exercised recovery runbook restores, validates, compiles, and compares
   an expected output from a clean environment.

## Explicit non-goals

This specification does not define SaaS tenancy, authorization, billing,
endpoints, cloud-provider implementation, R2 bucket layout, the exact
machine-readable snapshot schema, or the implementation ticket ordering. Those
are follow-up design and ticketing work constrained by this contract.

The full snapshot schema remains implementation-defined, but canonical
manifest serialization and its hash algorithm are versioned contract surface:
changing field order, encoding, or canonicalization is a breaking change to
release identity and requires explicit compatibility/migration handling;
existing `release_id` values must never be silently reinterpreted.

It does not rewrite FORMAT CARDs or transcripts, alter the canonical Realism
scale, infer clusters, or include raw media in the runtime snapshot.
