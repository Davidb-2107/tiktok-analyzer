# T008 — Run the shared mapping suite in public and private CI

Status: resolved
Type: implementation
Repository: `tiktok-analyzer-format-cards` + Vault repository
Blocked by: T006, T007

## Goal

Close the pre-push CI gap with one parameterized mapping test module. This
ticket wires and validates the public synthetic job and the private gate
workflow; exercising the private gate against a real pinned release is a
post-T009 release-readiness action owned by T011.

## Files

- Modify `test_subformula_mapping.py` to accept an explicit regime/source.
- Add the synthetic mapping note under
  `tests/fixtures/vault/wiki/analyses/`.
- Add `subformula_mapping_ref` and declared `channel_id` values to the two
  synthetic fixture formulas/transcripts.
- Modify `.github/workflows/ci.yml` to run the public mapping suite.
- Create the Vault workflow `.github/workflows/published-snapshot-gate.yml`
  for the private real-source gate.
- Add or modify the Vault-side invocation wrapper so both regimes call the
  same checked-out Analyzer test module.

## Acceptance criteria

- Public fixtures contain only synthetic handles, IDs, and mapping paths.
- Public CI executes the synthetic mapping suite; it does not skip because a
  real Vault is unavailable.
- The private Vault/release workflow checks out the Analyzer revision under
  test and requires an explicit authenticated `release_id` input. If that
  input or its source is absent, the workflow fails closed; this ticket does
  not claim that a real release has been exercised.
- Both regimes execute the same test module; the real-ID assertions are
  selected by explicit private regime configuration, not by a forked file.
- The private canonical gate has no `skipUnless`/silent skip path.
- The suite covers assigned, outlier, and analysis-only statuses, channel
  isolation, declared-ID/partition mismatch, and the poison test.
- A PR to `master` visibly runs the public job; the private result is recorded
  in the trusted release workflow rather than claimed as public CI. The
  actual private run with a pinned release is recorded by T011.

## Resolution

All acceptance criteria are satisfied: public CI runs the synthetic mapping
suite, the private workflow is explicit and fail-closed, both regimes execute
the same module, and the complete status/channel/poison coverage is present.
T011 records the real private run against the pinned release and its successful
result; no public job claims access to private Vault data.

## Out of scope

R2 object publication and the final branch promotion checklist are handled by
T009 and T011.
