# Deterministic Sub-formula Mapping — Implementation Plan

## Shipped contract

`--cluster` requires `--channel` and routes only through the selected channel
formula's `subformula_mapping_ref`. The approved mapping table is the sole
assignment authority; card values, visual style, Realism, hooks, and majority
statistics do not discover or merge formulas.

## Release gate

Run `test_subformula_mapping.py` with an explicit `VAULT_DIR` pointing to the
reviewed Vault. The canonical test fails when `VAULT_DIR`, the mapping note, or
the selected formula's mapping reference is unavailable. It also checks exact
IDs, `assigned`, `analysis_group_only`, and `outlier` statuses, plus
channel-scoped card and formula references.

## Workflow artifacts

`task-*-report.md` files for this deterministic-mapping work are versioned
release evidence. The T002, T003, T004, and T005 reports are therefore tracked.

## Limits

There is no automatic clustering, assignment of new cards, cross-channel
inference, or production use of `analysis_group_only` and outlier rows.
