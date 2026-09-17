# T001 — Publish the stable sub-formula mapping reference

Status: resolved
Repository: `Wiki_Claude`
Blocked by: none
Blocks: T002, T003

## Goal

Make the approved human mapping discoverable from each channel formula without
duplicating the video assignments or changing any FORMAT CARD.

## Scope

Add this frontmatter field to both channel formula documents:

```yaml
subformula_mapping_ref: wiki/analyses/2026-09-11-neon-psycho-clusters.md
```

The target must be the exact reviewed analysis note. Do not add a second
mapping file and do not rewrite the existing mapping table.

## Acceptance criteria

- Both `neon_psycho` channel formulas point to the same exact analysis note.
- The reference is relative to the Vault root and resolves from either formula.
- All FORMAT CARD files and transcript text remain unchanged.
- Vault registry/format validators pass.
- The change is made in the Vault worktree and is separately reviewable.

## Out of scope

Analyzer code, `--cluster`, automatic clustering, and changes to formula
assignments.

## Answer

Implemented in Vault commit `c7558aaf6227dbf2eefdef0d7fa38f29a156a712`.
Both `neon_psycho` Channel Formulas now point to
`wiki/analyses/2026-09-11-neon-psycho-clusters.md`. The Vault validator reports
10/10 valid cards; no FORMAT CARD or transcript changed. The pre-existing
analysis-note edit remains separate and uncommitted.

Review: independent task review approved; T002 is unblocked.
