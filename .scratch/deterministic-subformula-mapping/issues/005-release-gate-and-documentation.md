# T005 — Harden the release gate and reconcile documentation

Status: resolved
Repository: `tiktok-analyzer-format-cards`
Blocked by: none (T004 resolved)

## Goal

Make the real Vault mapping verification fail closed, then reconcile the
implementation and release documentation before the deterministic routing work
is considered ready to publish.

## Scope

- Make the canonical Vault test fail fast when `VAULT_DIR` or the referenced
  mapping is unavailable; it must never pass by silently skipping.
- Assert the canonical status values returned by the real Vault mapping,
  including `outlier` and `analysis_group_only`.
- Add direct regression assertions for channel-scoped `card_ref` and
  `formula_ref`, not only video IDs, channels, and statuses.
- Run the Analyzer unit/self-check suite, Vault validators, and relevant CI
  checks required by T001–T004.
- Correct the T003 report's test-count wording: `17 passed + 1 skipped`
  without `VAULT_DIR`, `18 passed` with it.
- Decide and document whether `task-*-report.md` files are versioned artifacts
  or workflow-local review artifacts, then make the repository state consistent.
- Update the implementation plan and release note with the shipped contract and
  known limits: deterministic, mapping-driven routing; no automatic clustering.

## Acceptance criteria

- A missing `VAULT_DIR` or mapping reference produces a failing test/check with
  an actionable error.
- The real Vault test proves the expected `outlier` and
  `analysis_group_only` statuses.
- Regression checks prove that `card_ref` and `formula_ref` never cross channel
  boundaries.
- Analyzer, Vault, and CI checks pass, with any unrelated pre-existing failure
  explicitly recorded.
- Documentation and tracked workflow artifacts use one consistent convention.
- Existing FORMAT CARD contents, transcripts, and the canonical mapping remain
  unchanged.

## Out of scope

Automatic clustering, FORMAT CARD rewrites, changes to the canonical `Realism`
scale, resolving `dark_psycho`, Stickman dates, voice calibration, or engine
validation.

## Answer

Implemented in Analyzer commit `37dbf4d` (base `bc2504e`). The real-Vault gate
now fails closed when `VAULT_DIR` or the canonical mapping is unavailable,
asserts `outlier` and `analysis_group_only`, and checks channel-scoped
`card_ref` and `formula_ref` provenance. The plan and release note document
deterministic mapping-driven routing and known limits. Task reports use one
consistent versioned-artifact convention.

Verification: without `VAULT_DIR`, the canonical gate fails with an actionable
error; with the T001 Vault worktree, 23/23 mapping tests, `test_brief_compiler`,
`brief_selfcheck`, and the Vault validator (10/10) pass. `git show --check`
passes. Bundled `pytest` is unavailable (`No module named pytest`) and is
recorded as an environment limitation. Independent review returned
Spec-compliance PASS and Task-quality APPROVED with no findings.

Final-review fix committed in `9496ef0`: duplicate canonical mapping sections
are now rejected instead of silently ignoring the second section, with a
regression test, and `CONTEXT.md` reflects the shipped `--cluster` behavior.
The scoped re-review approved both fixes. Final verification passed 23 mapping
tests, the compiler/self-checks, the Vault validator (10/10), and
`git show --check`.
