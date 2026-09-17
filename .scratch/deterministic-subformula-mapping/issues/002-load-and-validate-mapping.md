# T002 — Load and validate the approved mapping

Status: resolved
Repository: `tiktok-analyzer-format-cards`
Blocked by: none (T001 resolved)
Blocks: T003, T004

## Goal

Add one deterministic mapping loader behind the existing channel-scoped formula
selection. It must apply the human mapping and never infer a cluster.

## Scope

- Follow `subformula_mapping_ref` from the already selected channel formula.
- Read only the exact Markdown table under
  `## Décision — mapping canonique vidéo → sous-formula`.
- Validate `(niche, channel, video_id)` uniqueness, canonical channel values,
  disjoint channel membership, and known assignment statuses.
- Reject missing references, malformed rows, duplicate IDs, cross-channel IDs,
  and unknown status values with actionable errors.
- Preserve explicit `outlier` and `analysis_group_only` statuses.

## Acceptance criteria

- No filename/date globbing and no majority-based discovery.
- The loader returns the exact approved `neon_psycho` assignments from the Vault
  note when given either channel.
- A mapping row from the other channel is rejected, not silently ignored.
- Existing behavior without `--cluster` is unchanged.
- Unit tests cover valid rows and every rejection above.

## Out of scope

Brief output routing, new taxonomy fields, card edits, and automatic semantic
similarity.

## Answer

Implemented in Analyzer commit `a796db6` (base `6e0daa3`). The loader follows
the selected channel formula's exact `subformula_mapping_ref`, reads the
canonical mapping table, validates channel/video/status constraints, and keeps
explicit `outlier` and `analysis_group_only` assignments. It does not infer
clusters or use majority heuristics.

Verification: 13/13 focused mapping tests passed with the T001 Vault worktree
selected explicitly, and `test_brief_compiler.py` passed. Independent review
approved the implementation; two minor test-quality findings are deferred in
the T002 ledger. No FORMAT CARD, transcript, Vault, push, or merge was part of
T002.
