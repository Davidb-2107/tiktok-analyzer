# T005 report — release gate and documentation

## Result

The canonical real-Vault mapping test no longer skips. It requires an explicit
`VAULT_DIR` and the canonical mapping note, failing with an actionable message
when either is unavailable. With the reviewed T001 Vault worktree selected, it
checks exact IDs and statuses (`assigned`, `analysis_group_only`, and `outlier`)
for both channels, then directly asserts that compiled `format_card_ref` and
`channel_formula_ref` stay in that channel's directories.

No production routing, FORMAT CARD, transcript, canonical mapping, or Vault
content was changed.

## Documentation and artifacts

- Added the tracked implementation plan and release note documenting
  deterministic mapping-driven routing, the fail-closed release command, and
  known limits: no automatic clustering or automatic assignment.
- `task-*-report.md` is a versioned release-evidence convention for this work.
  T002, T003, T004, and this T005 report are tracked accordingly.
- Corrected T003's historical count to `17 passed + 1 skipped` without
  `VAULT_DIR`, and `18 passed` with its canonical Vault.

## Verification

- Intentional fail-closed proof: without `VAULT_DIR`, the canonical test fails
  with `release gate requires VAULT_DIR ... must not be skipped`.
- `VAULT_DIR=<T001 Wiki_Claude-clusters> python -B -m unittest -v
  test_subformula_mapping`: 22 passed.
- `VAULT_DIR=<T001 Wiki_Claude-clusters> python -B test_brief_compiler.py`:
  passed.
- `VAULT_DIR=<T001 Wiki_Claude-clusters> python -B brief_selfcheck.py`:
  passed.
- Vault validator: `format_card_registry.py --verify --niche neon_psycho`:
  `10 files - valid=10 missing=0 blocked=0 invalid=0 duplicate=0`.
- CI-equivalent fixture self-checks for `@ci` and `@fixture_b`, plus
  `brief_selfcheck.py`: passed.
- `git diff --check`: passed.

## Preserved external limitation

The CI backend command could not run in this desktop runtime because its bundled
Python has no `pytest` module. The failure is documented here; no test or gate
was skipped or weakened to conceal it.

## Final-review fix

- The canonical mapping parser now requires exactly one canonical section, so a
  conflicting duplicate cannot be ignored. CONTEXT now describes the shipped,
  mapping-driven `--cluster` behavior.
- Tests: 23 `test_subformula_mapping.py` cases with the T001 Vault, plus
  `test_brief_compiler.py`, `brief_selfcheck.py`, and `git diff --check` passed.
