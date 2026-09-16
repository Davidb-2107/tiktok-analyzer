# T006 — Implement channel identity allocation and declared partition checks

Status: resolved
Type: implementation
Repository: `tiktok-analyzer-format-cards`
Blocked by: none (T005 resolved)

## Goal

Make frozen `channel_id` an explicit record property, validate handle history
and collision rules, and move the loader's coherence check from current handle
to declared channel identity.

## Files

- Create `publication/identity.py`.
- Create `test_channel_identity.py`.
- Modify `brief_compiler.py` where registry frontmatter is loaded and the
  parent partition is checked.
- Modify the transcript fixture frontmatter used by the tests.

## Interfaces

`publication.identity` exposes:

```python
validate_channel_record(record: Mapping[str, object]) -> None
allocate_channel_id(project_id: str, handle: str, index: Mapping[str, object]) -> tuple[str, str]
validate_identity_index(index: Mapping[str, object]) -> None
```

The loader requires each published transcript to declare `channel_id` in
frontmatter and compares it with the partition directory. The migration
builder may write the field for legacy records; runtime loading never infers
it silently.

The loader consumes the canonical runtime payload produced by T005. Its
validation must use the checked-in schema as the source for required field
sets, rather than maintaining a second list of required names in Python.
Nested taxonomy and channel-record shapes are part of the validation surface;
presence of only the top-level keys is insufficient.

The resolved compilation-input record must also contain the required measured
values: `target_wpm` as one `decimal-v1` string,
`target_duration_s[]` and `shot_duration_s[]` as non-empty arrays of
`decimal-v1` strings. The validator rejects omission, wrong JSON types, and
empty measurement arrays; a payload cannot become valid by leaving these
fields out.

## Acceptance criteria

- Existing channels retain `handle[1:]` under `handle-slug-v1` when unused.
- A collision in one project allocates an opaque ID under `opaque-v1` and is
  recorded in the index with origin handle, release, actor, and evidence.
- `channel_id_scheme` is validated per channel, allowing mixed schemes in a
  project.
- History intervals use UTC bounds and reject overlap both within one channel
  and for one handle across different channels.
- `current_handle` must equal the open history interval.
- A transcript with an old handle and matching declared `channel_id` loads.
- A transcript with a tampered declared `channel_id` fails closed.
- Existing handle-prefixed `subformula_id` values remain unchanged and opaque.
- Tests cover `(project_id, channel_id, subformula_id)` uniqueness and the
  channel-scoped video assignment key.
- Tests prove the runtime schema and validator agree on required fields and
  reject malformed taxonomy/channel records.
- Tests reject a payload that omits any required resolved measurement or uses
  an empty measurement array.

## Out of scope

Persistent registry storage and publisher authentication are handled by T009.
The one-time migration of legacy Vault records is handled by T012.

## Answer

Implemented in commits `aab4fa3`, `33ab624`, `4fd75e4`, `6692a73`,
`8a42b7d`, and follow-up `d758423`.

- Frozen `channel_id` is required in transcript and formula frontmatter,
  compared with the partition directory, and used for transcript/formula
  references; current handles remain provenance rather than identity.
- `publication.identity` validates allocation schemes, collision evidence,
  UTC history intervals, both overlap invariants, current-handle projection,
  runtime taxonomy/channel shapes, scoped formula/video uniqueness, and
  required non-empty decimal-v1 measurements.
- The checked-in snapshot schema is the source of required runtime and
  resolved-input field sets; both manifest and identity validators consume it.
- Tests cover old-handle continuity, tampering, formula routing, collisions,
  mixed schemes, interval boundaries, uniqueness, malformed runtime data, and
  release-path measurement omissions.
- Runtime formulas and mappings now require a declared project channel,
  nested identity records cannot contradict their enclosing project, and
  channel-record extra fields are rejected consistently.

Verification: 31 focused identity/manifest tests passed, the synthetic
compiler smoke passed, schema parsing and `git diff --check` passed, and the
follow-up adversarial review returned `PASS` with no findings.

The real Vault remains intentionally unchanged; its legacy records still need
the declared `channel_id` migration in T012 before the private real-Vault gate
can run. The public synthetic mapping gate also remains outside this ticket
until its canonical mapping fixture is supplied.
