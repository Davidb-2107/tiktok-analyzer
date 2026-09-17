# T007 — Add explicit source adapters and draft/release equivalence

Status: resolved
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
resolved `wpm_source` string required by the published brief. It decodes
`decimal-v1` strings to the numeric types expected by the existing brief
schema, so the internal payload representation does not change brief output.

## Acceptance criteria

- Missing or malformed source context fails with an actionable error.
- Local development uses a draft produced by the same builder path as a
  published release.
- A local draft and release built from the same `vault_commit` and
  `builder_version` compile to byte-identical JSON.
- No absolute filesystem path occurs in the brief output.
- `script.wpm_source` remains byte-exact and transcript verbatim is excluded
  from the snapshot.
- The source adapter refuses an incomplete runtime payload: it must receive
  `target_wpm`, `target_duration_s[]`, and `shot_duration_s[]` before compiling
  either a draft or a release.
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

## Answer

Implemented explicit `local:<draft-path>` and `release:<release_id>` source
adapters, strict snapshot verification, byte-equivalence coverage, exact
`wpm_source` preservation, transcript-poison protection, required resolved
measurements, and absolute-path rejection. Runtime compilation no longer
discovers `VAULT_DIR`; the remaining Vault path is an explicit builder-only
seam.

The builder-only seam is transitional: after T009 publishes the first real
release, T008 switches the mapping gate to the pinned `release:` context and
the legacy Vault compilation seam is removed before final promotion. It is not
a second runtime source.

Independent adversarial review: PASS, no remaining findings. Verification:
37 focused source/identity/manifest tests, 23/23 real-Vault mapping tests with
the T012 migration, fixture and real-Vault compiler smoke tests, and
`git diff --check`.
