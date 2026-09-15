# Task 1 report — Separate real and fixture smoke modes

## Status

Implemented the harness-only discriminator. `test_brief_compiler.py` now runs
`_test_channel_formula_routing()` only when `FORMAT_CARD_TEST_CHANNEL` is one
of the two explicit fixture channels: `@ci` or `@fixture_b`.

## Commit

- `6f0f483 test: scope formula routing smoke to fixtures`

## Files changed

- `test_brief_compiler.py`

No compiler, Vault, backend-test, or CI-workflow files changed.

## Validation

Bundled runtime used:
`C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`

Pre-change red check:

```text
VAULT_DIR=C:/Users/dbele/Documents/Codex/2026-09-11/referenced-chatgpt-conversation-this-is-an-2/work/Wiki_Claude-clusters C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B test_brief_compiler.py
ValueError: [neon_psycho] chaîne introuvable: @ci; disponibles: @the.wisejourney, @viraldtoprw
```

Executed commands and outputs:

```text
VAULT_DIR=C:/Users/dbele/Documents/Codex/2026-09-11/referenced-chatgpt-conversation-this-is-an-2/work/Wiki_Claude-clusters C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B test_brief_compiler.py
FAIL: AssertionError in _test_cp1252_warning; its dark_psycho child process returns nonzero.

VAULT_DIR=tests/fixtures/vault FORMAT_CARD_TEST_CHANNEL=@ci C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B test_brief_compiler.py
OK — brief_compiler : brief neon_psycho valide, couplé SOT + ENGINE-FACTS + profil voix.
  beats: 4 (68.5s)  shots: 25  wpm: 180.0 (ci_voice_v1)

VAULT_DIR=tests/fixtures/vault FORMAT_CARD_TEST_CHANNEL=@fixture_b C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B test_brief_compiler.py
OK — brief_compiler : brief neon_psycho valide, couplé SOT + ENGINE-FACTS + profil voix.
  beats: 4 (68.5s)  shots: 25  wpm: 180.0 (ci_voice_v1)

VAULT_DIR=C:/Users/dbele/Documents/Codex/2026-09-11/referenced-chatgpt-conversation-this-is-an-2/work/Wiki_Claude-clusters C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B brief_selfcheck.py
OK — brief.schema.json : structure valide, contrat couplé au SOT.
  target_duration_s = [62.0, 75.0]  shot_duration_s = [1.5, 4.0]  (SOT réel)
  shots: 3  beats: 4  prompts: 2

git diff --check
PASS (no diff-check output; Git emitted only existing CRLF/ignore warnings)
```

## Concerns

The post-change real `test_brief_compiler.py` reaches `_test_cp1252_warning`,
then its `dark_psycho` compile fails because the merged Vault contains a
root-level transcript where the compiler expects `darkpsychology1100/`. This
is Vault data outside the task scope. The standalone real `brief_selfcheck.py`
and both fixture routing modes pass; the full real compiler smoke does not.

## Round 1 fix report

### Status

Implemented the minimum harness-only fix requested by review. The
`_test_cp1252_warning()` check is now available only when
`RUN_DARK_PSYCHO_SMOKE=1`; the default real/channel smoke skips that
dark_psycho-specific validation, while `@ci` and `@fixture_b` still run their
synthetic routing assertions.

### Commit

- `72da043 test: opt in dark psycho smoke`

### Files changed

- `test_brief_compiler.py`
- `.superpowers/sdd/2026-09-15-analyzer-real-vault-smoke/task-1-report.md`

The report append is documentation only. Compiler, Vault, backend-test, and
CI-workflow behavior remain unchanged.

### Exact commands and outputs

All commands below use the bundled executable explicitly:
`C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

```text
VAULT_DIR=C:/Users/dbele/Documents/Codex/2026-09-11/referenced-chatgpt-conversation-this-is-an-2/work/Wiki_Claude-clusters C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B test_brief_compiler.py
OK — brief_compiler : brief neon_psycho valide, couplé SOT + ENGINE-FACTS + profil voix.
  beats: 3 (68.5s)  shots: 25  wpm: 215.0 (aFP1SKN7mTGVQWmfczLk)

VAULT_DIR=tests/fixtures/vault FORMAT_CARD_TEST_CHANNEL=@ci C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B test_brief_compiler.py
OK — brief_compiler : brief neon_psycho valide, couplé SOT + ENGINE-FACTS + profil voix.
  beats: 4 (68.5s)  shots: 25  wpm: 180.0 (ci_voice_v1)

VAULT_DIR=tests/fixtures/vault FORMAT_CARD_TEST_CHANNEL=@fixture_b C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B test_brief_compiler.py
OK — brief_compiler : brief neon_psycho valide, couplé SOT + ENGINE-FACTS + profil voix.
  beats: 4 (68.5s)  shots: 25  wpm: 180.0 (ci_voice_v1)

VAULT_DIR=C:/Users/dbele/Documents/Codex/2026-09-11/referenced-chatgpt-conversation-this-is-an-2/work/Wiki_Claude-clusters C:/Users/dbele/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B brief_selfcheck.py
OK — brief.schema.json : structure valide, contrat couplé au SOT.
  target_duration_s = [62.0, 75.0]  shot_duration_s = [1.5, 4.0]  (SOT réel)
  shots: 3  beats: 4  prompts: 2

git diff --check
PASS (no diff-check output)
```

### Concerns

`RUN_DARK_PSYCHO_SMOKE=1` preserves the separate dark_psycho cp1252 check,
but that opt-in check still exposes the pre-existing merged-Vault path
inconsistency described above. It is intentionally not changed here.
