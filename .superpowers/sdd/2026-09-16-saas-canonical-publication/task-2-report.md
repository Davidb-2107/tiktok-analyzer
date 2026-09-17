# T006 — Channel identity registry and declared partition checks

## Scope

Implemented the T006 channel identity and loader contract only. The loader now
requires a declared frozen `channel_id`, compares it with the partition
directory, and preserves the historical/current handle separately. The real
Vault was not modified.

## Implementation

- `publication/identity.py`
  - validates frozen channel records and UTC handle-history intervals;
  - rejects overlap within a channel and for one handle across channel IDs;
  - enforces the open-interval `current_handle` projection;
  - allocates handle-slug IDs or deterministic opaque collision IDs with
    per-channel schemes;
  - validates audited identity-index records and mixed schemes;
  - sources runtime required fields from `publication/snapshot.schema.json`;
  - validates taxonomy/channel shapes, scoped formula/video uniqueness, and
    required non-empty canonical decimal measurements.
- `brief_compiler.py`
  - requires `channel_id` frontmatter and checks it against the partition;
  - returns `channel_id` in loaded video records.
- `test_channel_identity.py`
  - focused acceptance tests for identity allocation/history, runtime shape,
    uniqueness, and old-handle/declared-partition loading.
- `test_brief_compiler.py` and the two checked-in synthetic transcript fixtures
  - minimal declared-identity frontmatter updates.

## Verification

| Check | Result |
| --- | --- |
| `python -m unittest -v test_channel_identity.py` | 12 tests passed |
| `python -m unittest -v test_channel_identity.py test_publication_manifest.py` | 27 tests passed |
| `VAULT_DIR=tests/fixtures/vault FORMAT_CARD_TEST_CHANNEL=@ci python test_brief_compiler.py` | passed; assert-based compiler smoke |
| `git diff --check` | passed |

The existing `test_subformula_mapping.py` suite was also checked against the
synthetic fixture: 22 of 23 tests passed. Its one failure is the pre-existing
private-Vault gate requiring the canonical mapping at
`tests/fixtures/vault/wiki/analyses/2026-09-11-neon-psycho-clusters.md`; that
fixture is outside T006 scope and was not added or changed.

## Changed files

- `publication/identity.py`
- `brief_compiler.py`
- `test_channel_identity.py`
- `test_brief_compiler.py`
- `tests/fixtures/vault/Projects/Sourcing/transcripts/neon_psycho/ci/1234567890123456789.md`
- `tests/fixtures/vault/Projects/Sourcing/transcripts/neon_psycho/fixture_b/2234567890123456789.md`
- `.superpowers/sdd/2026-09-16-saas-canonical-publication/task-2-report.md`

## Concerns

The default real-Vault compiler smoke remains intentionally unavailable until
legacy transcripts receive their declared `channel_id`; modifying those real
cards/transcripts was explicitly out of scope. The checked-in synthetic Vault
path passes the compiler smoke without that migration.

## Adversarial review fix round

The loader now builds transcript references from the declared frozen
`channel_id`, identity-index records require an explicit `current_handle`,
runtime payload wrappers reject schema-disallowed top-level fields, and the
runtime required-field set is loaded by a shared schema helper used by both
T005 and T006. The old-handle loader test asserts the frozen-ID reference.

Final fix-round verification:

| Check | Result |
| --- | --- |
| `python -m unittest -v test_channel_identity.py test_publication_manifest.py` | 29 tests passed |
| `VAULT_DIR=tests/fixtures/vault FORMAT_CARD_TEST_CHANNEL=@ci python test_brief_compiler.py` | passed; fixture compiler smoke |
| `git diff --check` | passed |

Fix-round changed files:

- `publication/manifest.py`
- `publication/identity.py`
- `brief_compiler.py`
- `test_channel_identity.py`
- `.superpowers/sdd/2026-09-16-saas-canonical-publication/task-2-report.md`

## Final formula-routing P1 fix

`find_formula` now requires a nonempty shared frozen `channel_id` on selected
videos, requires every candidate formula to declare `channel_id`, requires the
formula filename stem to equal that declared ID, and selects only by that ID.
Historical `channel` text remains in provenance and is not used as identity.
Temporary/public formula fixtures and mapping-test video records now declare
their frozen IDs. The renamed-channel regression asserts both transcript and
formula references use `frozen-id`, not `old_handle`.

Final verification:

| Check | Result |
| --- | --- |
| `python -m unittest -q test_channel_identity.py test_publication_manifest.py` | 29 tests passed |
| `VAULT_DIR=tests/fixtures/vault FORMAT_CARD_TEST_CHANNEL=@ci python test_brief_compiler.py` | passed; fixture compiler smoke |
| `python -m unittest -q test_subformula_mapping.py` | 22 passed, 1 pre-existing fixture-gate failure |
| `git diff --check` | passed |

Final fix changed files:

- `brief_compiler.py`
- `test_brief_compiler.py`
- `test_channel_identity.py`
- `test_subformula_mapping.py`
- `tests/fixtures/vault/Projects/Sourcing/formats/neon_psycho/ci.md`
- `tests/fixtures/vault/Projects/Sourcing/formats/neon_psycho/fixture_b.md`
- `.superpowers/sdd/2026-09-16-saas-canonical-publication/task-2-report.md`

The final strict-ID guard rerun recorded 29 passing focused T006/T005 tests;
the fixture compiler smoke and diff check remained passing. The existing
mapping suite remained 22/23 because its one release-gate test requires the
canonical mapping file absent from the checked-in synthetic Vault.
