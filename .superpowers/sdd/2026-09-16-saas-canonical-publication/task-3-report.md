# T007 — Source adapters and draft/release equivalence

## Scope

Runtime compilation now consumes an explicit local draft or pinned release
snapshot. The Vault path remains only as an explicit builder seam until the
first real release and the T008 gate cutover.

## Implementation

- `publication/source.py`
  - parses `local:<draft-path>` and `release:<release_id>` contexts;
  - requires an injected release root;
  - verifies canonical manifest/payload bytes and the pinned release ID;
  - validates runtime shape and measurements, preserves `wpm_source`, and
    rejects transcript verbatim.
- `brief_compiler.py`
  - requires `source_context` for runtime compilation;
  - exposes explicit builder-only Vault configuration;
  - keeps channel and subformula routing unchanged.
- `brief_selfcheck.py`
  - requires an explicit snapshot for runtime self-checks;
  - removes the author-machine default and keeps SOT loading explicit for the
    builder seam.
- Tests cover local/release equivalence, poison transcripts, absolute paths,
  canonical bytes, required measurements, and existing routing.

## Verification

| Check | Result |
| --- | --- |
| Source/identity/manifest focused suite | 37 tests passed |
| Real Vault mapping gate with T012 migration | 23/23 passed |
| Synthetic fixture compiler smoke | passed |
| Real Vault compiler smoke | passed |
| `git diff --check` | passed |
| Independent adversarial review | PASS; no remaining findings |

## Transition

The mapping suite currently exercises the explicit builder seam for the real
Vault smoke because T009 has not published a release yet. T008 must switch
that gate to an authenticated pinned `release:` context after T009, then the
legacy Vault compilation seam can be deleted before final promotion.
