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
| `python -m unittest -v test_channel_identity.py test_publication_manifest.py` | 28 tests passed |
| `VAULT_DIR=tests/fixtures/vault FORMAT_CARD_TEST_CHANNEL=@ci python test_brief_compiler.py` | passed; fixture compiler smoke |
| `git diff --check` | passed |

Fix-round changed files:

- `publication/manifest.py`
- `publication/identity.py`
- `brief_compiler.py`
- `test_channel_identity.py`
- `.superpowers/sdd/2026-09-16-saas-canonical-publication/task-2-report.md`
