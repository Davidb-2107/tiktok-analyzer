# T003 — Add deterministic `--cluster` routing

Status: resolved
Repository: `tiktok-analyzer-format-cards`
Blocked by: none (T002 resolved)
Blocks: T004

## Goal

Allow a caller to request a production sub-formula only after selecting one
channel, using the approved mapping as the sole routing authority.

## Scope

- Add the smallest CLI/API surface needed for `--cluster <subformula_id>`.
- Require `--channel` for every cluster request.
- Resolve only video IDs assigned to the requested sub-formula in that channel.
- Reject partial, ambiguous, cross-channel, unknown, or unassigned selections.
- Reject `analysis_group_only` as a production formula and preserve outliers as
  explicitly unassigned.
- Keep `source.channel`, card references, and formula references channel-scoped.

## Acceptance criteria

- `@viraldtoprw` resolves its two approved sub-formulas independently.
- `@the.wisejourney` resolves `wise_provocative_relationship_claim`.
- `wise_pattern_interrupt_shock` is not routable as a production formula.
- `7589746128195783958` remains an outlier and produces no guessed formula.
- The same style/Realism values across channels never affect routing.
- Existing non-cluster compilation remains backward compatible.

## Out of scope

Automatic clustering, majority voting, FORMAT CARD rewrites, and changes to the
canonical `Realism` scale.

## Answer

Implemented in Analyzer commit `7dc67ef` (base `a796db6`). The new
`--cluster <subformula_id>` route requires `--channel`, uses the approved
mapping as its sole authority, returns only exact channel-scoped assignments,
rejects partial/ambiguous/cross-channel/unknown selections, rejects
`analysis_group_only` for production, and preserves outliers as explicitly
unassigned. Existing non-cluster compilation remains unchanged.

Verification: 18/18 mapping tests passed with the T001 Vault worktree selected,
`test_brief_compiler.py` passed, and `git diff --check` passed. Independent
review returned Spec-compliance PASS and Task-quality APPROVED with no findings.
No FORMAT CARD, transcript, Vault, push, or merge was part of T003.
