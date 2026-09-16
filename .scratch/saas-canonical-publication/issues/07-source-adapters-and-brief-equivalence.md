# T007 — Add explicit source adapters and draft/release equivalence

Status: open
Type: implementation
Repository: `tiktok-analyzer-format-cards`
Blocked by: T005, T006

## Goal

Replace implicit Vault discovery with explicit draft/release source contexts,
then prove that the same approved source built with the same builder produces
the same brief through both paths.

## Files

- Create `publication/source.py`.
- Create `test_source_context.py`.
- Modify `brief_compiler.py` to consume the resolved source adapter.
- Modify `brief_selfcheck.py` to require an explicit source context and remove
  the author-machine default.
- Extend `test_brief_compiler.py` with the equivalence and absolute-path tests.

## Interfaces

`publication.source` exposes:

```python
parse_source_context(value: str) -> SourceContext
resolve_source(context: SourceContext) -> SnapshotSource
```

Supported contexts are `local:<draft-path>` and `release:<release_id>`.
`VAULT_DIR` is accepted only by the builder that creates a local draft; the
compiler and backend never discover it from their environment.

The adapter supplies the canonical `payload.json` runtime object. It never
reconstructs fractional values from binary floats, and it preserves the exact
resolved `wpm_source` string required by the published brief.

## Acceptance criteria

- Missing or malformed source context fails with an actionable error.
- Local development uses a draft produced by the same builder path as a
  published release.
- A local draft and release built from the same `vault_commit` and
  `builder_version` compile to byte-identical JSON.
- No absolute filesystem path occurs in the brief output.
- `script.wpm_source` remains byte-exact and transcript verbatim is excluded
  from the snapshot.
- The poison test changes source transcript text while keeping all compiled
  inputs constant and proves identical output; if output changes, the test
  fails.
- Existing `--channel` and `--cluster` routing behavior remains unchanged.
- The shared source module reads canonical bytes strictly: duplicate JSON keys
  and non-canonical manifest/payload bytes fail closed instead of being
  silently reserialized.

## Out of scope

Publisher workflow, R2 credentials, public/private CI wiring, and `/hub`
migration are handled by T008–T010.
