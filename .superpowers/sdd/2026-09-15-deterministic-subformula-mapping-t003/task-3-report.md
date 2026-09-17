# T003 implementation report — deterministic `--cluster` routing

## Delivered

- Added `route_subformula(videos, cluster)`, which calls
  `load_subformula_mapping(videos)` and uses only its validated approved rows.
- Added `cluster=` to `compile_brief()` and `_compile_brief_full()`.
  Cluster use requires a selected channel, then compiles only the exact assigned
  video IDs through the existing brief pipeline.
- Added CLI `--cluster SUBFORMULA`; it requires `--channel` and includes the
  cluster in the default output filename.
- Preserved non-cluster behavior: `cluster=None` follows the prior registry and
  compilation flow unchanged.

## Routing rules

- Exact assignment IDs only; prefixes and unknown IDs are rejected.
- `analysis_group_only` and `outlier` assignments are rejected as non-production.
- Partial and cross-channel input selections fail through the T002 complete-table
  validation before routing.
- The routed videos retain the selected channel's existing card and formula
  references; no style, Realism, hook, formula, or card data is used to select a
  sub-formula.

## Tests

`test_subformula_mapping.py` adds coverage for:

- both approved `@viraldtoprw` groups and their exact disjoint ID sets;
- the approved `@the.wisejourney` relationship-claim group;
- rejection of `wise_pattern_interrupt_shock`, the explicit outlier video, and
  non-exact/unknown IDs;
- rejection of partial and cross-channel selections;
- API and CLI rejection when `--cluster` lacks `--channel`.

TDD evidence: before implementation, the new routing tests failed with three
missing `route_subformula` attributes and one unsupported `cluster` keyword.
After implementation, the focused suite passed.

## Verification and self-review

- `test_subformula_mapping.py`: 17 passed + 1 skipped without `VAULT_DIR`; 18
  passed with the canonical Vault selected.
- `test_brief_compiler.py`: passed.
- `git diff --check`: passed.
- Reviewed the final diff: only `brief_compiler.py`, its focused tests, and this
  required report are staged; no FORMAT CARD, transcript, Vault, canonical
  mapping, or unrelated planning file changes were made.
