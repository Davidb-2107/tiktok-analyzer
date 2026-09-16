# T005 — Snapshot manifest and release identity

## Scope

Implemented only the snapshot manifest runtime, its JSON Schema, and focused
standard-library tests:

- `publication/__init__.py`
- `publication/manifest.py`
- `publication/snapshot.schema.json`
- `test_publication_manifest.py`

The runtime uses canonical UTF-8 JSON (`sort_keys=True`, compact separators,
`ensure_ascii=False`, `allow_nan=False`) and labels SHA-256 values as
`sha256:<lowercase-hex>`. `release_id_for` validates the v1 manifest and hashes
a shallow manifest copy with `release_id` removed. `verify_release` validates
the manifest, recomputes that address independently, compares both the pinned
and embedded IDs, then compares the payload digest.

Schema v1 requires the project identity, release identity, version markers,
payload digest, resolved runtime inputs, and the required provenance fields:
Vault commit, builder version, taxonomy/module digests, voice-profile digest,
identity history, and build-time freshness.

## TDD evidence

The focused test was written before `publication/` existed:

```text
Command:
C:\Users\dbele\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest test_publication_manifest.py

Output:
ModuleNotFoundError: No module named 'publication'
Ran 1 test in 0.001s
FAILED (errors=1)
```

After the implementation, the focused suite passed:

```text
Command:
C:\Users\dbele\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest test_publication_manifest.py

Output:
.....
----------------------------------------------------------------------
Ran 5 tests in 0.001s

OK
```

The tests cover deterministic byte output and Unicode, hand-derived
non-circular release identity, matching verification, manifest/payload/pinned
ID mutation failures, plus NaN and unsupported schema/hash versions.

## Relevant existing checks

```text
Command:
C:\Users\dbele\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m json.tool publication/snapshot.schema.json

Result: exit 0; JSON parsed successfully.
```

```text
Command:
C:\Users\dbele\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest test_subformula_mapping.py

Output:
F......................
Ran 23 tests in 0.738s
FAILED (failures=1)

Failure: test_approved_vault_mapping_resolves_exact_channel_sets
release gate requires VAULT_DIR pointing at the canonical Vault; the real
mapping check must not be skipped
```

This pre-existing, private-Vault-dependent gate cannot run in this worktree
because `VAULT_DIR` is unset. It is unrelated to the new standard-library
publication module; no test was skipped or changed to conceal it.

## Constraints observed

- No dependencies added.
- No Vault access, identity allocation, uploads, source adapters, backend
  changes, or brief compilation implemented.
- No unrelated files were modified or reverted.
