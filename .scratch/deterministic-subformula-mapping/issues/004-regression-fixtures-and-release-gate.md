# T004 — Add routing fixtures and regression coverage

Status: resolved
Repository: `tiktok-analyzer-format-cards`
Blocked by: none (T003 resolved)
Blocks: T005

## Goal

Prove with focused fixtures that deterministic sub-formula routing preserves
channel isolation and cannot regress into implicit discovery.

## Scope

- Add a minimal fixture mapping for two channels with different styles,
  Realism values, hooks, formulas, and one outlier.
- Test exact channel/sub-formula ID sets, reference qualification, and all
  invalid mapping failures.
- Add a direct mixed-status fixture proving that one `subformula_id` with
  non-uniform statuses is rejected as `ambiguous`.
- Test that common visual values do not merge formulas.

## Acceptance criteria

- Tests prove no cross-channel inheritance of style, Realism, hook, card ref, or
  formula ref.
- Tests prove no partial formula is selected.
- The focused regression suite and `git diff --check` pass.
- Existing FORMAT CARD contents remain unchanged.
- The invalid-mapping suite directly exercises the `ambiguous` status rejection.

## Out of scope

Vault release-gate hardening, CI/release-note reconciliation, resolving
`dark_psycho`, Stickman dates, voice calibration, engine validation, or the
future inverted Realism migration.

## Answer

Implemented in Analyzer commit `bc2504e` (base `7dc67ef`). Added focused
two-channel fixtures and regression coverage for exact routing sets, partial and
cross-channel selections, shared visual values, outliers, analysis-only groups,
and a direct mixed-status `ambiguous` rejection. Existing FORMAT CARDs,
transcripts, Vault data, and production behavior were unchanged.

Verification: without `VAULT_DIR`, 21 tests passed and 1 optional real-Vault
test was skipped; with the T001 Vault worktree, 22/22 tests passed.
`test_brief_compiler.py` and `git diff --check` passed. Independent review
returned Spec-compliance PASS and Task-quality APPROVED with no findings.
T005 remains responsible for the real-Vault fail-fast gate and documentation
reconciliation.
