# T006 — Implement channel identity allocation and declared partition checks

Status: open
Type: implementation
Repository: `tiktok-analyzer-format-cards`
Blocked by: T005

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

Persistent registry storage, publisher authentication, and physical Vault
migration are handled by T009.
