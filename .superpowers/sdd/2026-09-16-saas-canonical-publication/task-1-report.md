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

## Fix round — payload boundary and json-c14n-v1

The fix separates the runtime-only canonical `payload.json` from the
release/provenance-only `manifest.json`. It adds strict `json-c14n-v1`
canonicalization: ASCII keys sorted by raw UTF-8 bytes, NFC strings,
integer-only numbers, canonical UTF-8 JSON bytes, duplicate-key rejection,
and rejection of non-canonical stored payload bytes. Provenance now requires
the exact `sot_versions` field. Versioned known-answer vectors cover key order,
NFC normalization, decimal strings, escaping/UTF-8 bytes, duplicate keys,
floats, and negative zero.

Focused verification:

```text
Command:
C:\Users\dbele\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest test_publication_manifest.py

Output:
.........
----------------------------------------------------------------------
Ran 9 tests in 0.011s

OK
```

```text
Command:
git diff --check

Result: exit 0; no whitespace errors.
```

Fix commit changed files:

- `publication/__init__.py`
- `publication/manifest.py`
- `publication/snapshot.schema.json`
- `publication/canonicalization-v1-vectors.json`
- `test_publication_manifest.py`

The existing private-Vault-dependent `test_subformula_mapping.py` gate was
not rerun in this fix round; its prior failure is recorded above and remains
outside T005's scope.

## P1 review fixes

The payload validator now requires all six runtime fields named by the checked-
in schema: `taxonomy`, `channels`, `formulas`, `cards`, `mappings`, and
`resolved_compilation_inputs`. `parse_manifest_bytes` strictly parses stored
manifest bytes with duplicate-key and canonical-byte rejection, and
`verify_release` accepts those bytes directly so release identity cannot be
computed from silently normalized storage.

Focused verification:

```text
Command:
C:\Users\dbele\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest test_publication_manifest.py

Output:
..............
----------------------------------------------------------------------
Ran 14 tests in 0.011s

OK
```

```text
Command:
git diff --check

Result: exit 0; no whitespace errors.
```

P1 fix commit changed files:

- `publication/__init__.py`
- `publication/manifest.py`
- `test_publication_manifest.py`
