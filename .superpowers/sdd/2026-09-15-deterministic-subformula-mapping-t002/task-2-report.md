# T002 — Load and validate the approved mapping

Status: complete

## Implementation

- Added `load_subformula_mapping(videos)` to `brief_compiler.py`.
- Follows `subformula_mapping_ref` from the already selected, channel-scoped
  formula and resolves only that exact Vault path.
- Reads only the exact table under
  `## Décision — mapping canonique vidéo → sous-formula`.
- Validates the mapping note niche, table shape/separator, non-empty cells,
  TikTok video IDs, canonical channel handles, duplicate IDs, cross-channel
  IDs, selected-video coverage, and sub-formula group size.
- Returns only rows for the selected channel while preserving `assigned`,
  `analysis_group_only`, and `outlier` statuses. No mapping-note globbing,
  card/majority inference, or `--cluster` routing was added.
- Corrected the pre-existing contradictory outlier test assertions without
  removing its coverage.

## Verification

Selected formulas in the explicit Vault worktree both contain:

```yaml
subformula_mapping_ref: wiki/analyses/2026-09-11-neon-psycho-clusters.md
```

Canonical focused test:

```text
VAULT_DIR='C:/Users/dbele/Documents/Codex/2026-09-11/referenced-chatgpt-conversation-this-is-an-2/work/Wiki_Claude-clusters' \
'C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m unittest -v test_subformula_mapping.py
Ran 13 tests — OK
```

Existing compiler regression:

```text
'C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B test_brief_compiler.py
Passed
```

Commit: `a796db624e9fa265cefab59aacb3ce82d025f74c`

Only `brief_compiler.py` and `test_subformula_mapping.py` were committed. Vault
files, FORMAT CARDs, transcripts, planning/spec files, and the existing
untracked workflow artifacts were not modified or staged. No push or merge was
performed.

## Concerns

Git emitted a non-fatal `packed-refs.lock` permission message during commit;
the commit was written and verified at the SHA above. The worktree still shows
only the pre-existing untracked scratch/spec/progress artifacts.
