# T008 — Run the shared mapping suite in public and private CI

Status: open
Type: implementation
Repository: `tiktok-analyzer-format-cards` + Vault repository
Blocked by: T006, T007

## Goal

Close the pre-push CI gap with one parameterized mapping test module: public
CI validates synthetic fixtures, while trusted Vault/release CI validates the
approved real snapshot without exposing real identities to public pull
requests.

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
- Private Vault/release CI checks out the Analyzer revision under test,
  supplies an authenticated pinned release, and fails when the real source is
  absent or malformed.
- Both regimes execute the same test module; the real-ID assertions are
  selected by explicit private regime configuration, not by a forked file.
- The private canonical gate has no `skipUnless`/silent skip path.
- The suite covers assigned, outlier, and analysis-only statuses, channel
  isolation, declared-ID/partition mismatch, and the poison test.
- A PR to `master` visibly runs the public job; the private result is recorded
  in the trusted release workflow rather than claimed as public CI.

## Out of scope

R2 object publication and the final branch promotion checklist are handled by
T009 and T011.
