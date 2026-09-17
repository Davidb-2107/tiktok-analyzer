# T004 report — regression fixtures and release gate

## Result

Implemented focused regression coverage in `test_subformula_mapping.py` only.
No production routing, FORMAT CARD, transcript, Vault, or release-gate code was changed.

## Coverage added

- A two-channel mapping fixture with distinct style, Realism, hook, formula IDs,
  and an explicit outlier proves both channel formula routes select their exact
  video sets and never select the outlier.
- A same-style/same-Realism/same-hook fixture proves visual commonality cannot
  merge `@alpha` and `@beta` formulas.
- A direct mixed-status fixture (`alpha_formula` and `alpha_formula*`) proves
  the production route rejects the shared `subformula_id` as `ambiguous`.
- A mapping reference escaping the configured Vault is rejected explicitly.

Existing focused tests continue to cover partial selections, cross-channel
records, malformed/duplicate/missing mappings, unknown assignments, outliers,
and analysis-only assignments.

## Verification

- `python -m unittest -v test_subformula_mapping.py`: 21 passed, 1 skipped
  (`VAULT_DIR` is not configured, so the optional real-Vault mapping test is
  skipped).
- `python test_brief_compiler.py`: passed.
- `git diff --check`: passed.

## Self-review

The tests assert observable routing results using literal IDs. A mutation that
groups formulas by shared visual fields, allows an outlier, allows the mixed
status assignment, permits an escaping mapping reference, or returns a partial
set fails at least one focused check. T005 work (real-Vault fail-fast gate,
CI/release notes, and report convention) remains untouched.
