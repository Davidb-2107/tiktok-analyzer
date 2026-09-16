# Decide Analyzer and CI consumption

Status: resolved
Type: grilling
Blocked by: none (01 resolved)

## Question

How should the Analyzer, CI, and future workers consume the published
canonical snapshot while the local Vault workflow remains available during the
migration?

The decision must cover the consumer interface, local versus published source
selection, fixture/snapshot strategy for CI, compatibility and cutover, and
fail-closed behavior when a snapshot is missing, stale, malformed, or mixes
channels. It must preserve the existing deterministic `--channel` and
`--cluster` guarantees.

The migration comparison must enumerate the allowed volatile output fields
before claiming that local-Vault and published-snapshot compilation are
identical. A test must compare all other JSON fields explicitly. Published
artifact names must not depend on mutable handles, and the consumer must verify
both the taxonomy semantic version and authoritative-module digest.

The equivalence suite must also replace source transcript text with a poison
sentinel and assert byte-identical output. A failure means the published
payload boundary must be reopened. Backend transcript display is not a reason
to add verbatim text to the Analyzer snapshot.

Control ownership must be explicit. The consumer verifies payload-hash versus
manifest, schema, internal cross-record consistency, and whether the declared
version is within its supported compatibility range. A bad hash, schema, or
malformed snapshot fails closed. The publisher/private CI alone compares the
snapshot with the current SOT/taxonomy authorities and computes the
authoritative-module digest; the consumer cannot independently re-run those
checks after decoupling from the Vault. Publisher-produced freshness results
are carried as machine-readable manifest fields. A valid but older snapshot
may load without automatic refresh; a separate caller policy may reject it for
production while preserving reproducibility.

The public CI must not carry the real-identity denylist. Trusted private CI or
the Vault pre-push hook performs that scan; public CI enforces only a synthetic
fixture contract and must never expose real handles, video IDs, or mapping-note
paths.

The release manifest's approver fields must come from the authenticated
GitHub Actions actor (`actor_id` and login), not user-provided text.

The manifest's `freshness` is explicitly an immutable state measured at build
time, not a claim about the current authority. If current freshness is needed,
a private periodic auditor updates a separate mutable, audited index keyed by
`release_id`; it never rewrites the snapshot manifest.

## Answer

T03 resolves Analyzer and CI consumption as follows.

- Source selection is mandatory and explicit through an opaque adapter handle,
  such as `local:<path>` for a draft snapshot or `release:<id>` for a published
  snapshot. Missing or malformed context fails explicitly. `VAULT_DIR` exists
  only inside the builder; hard-coded author-machine defaults and runtime
  fallback to a local Vault are forbidden.
- The public CI and trusted private CI use one parameterized test module. Public
  CI runs synthetic mapping fixtures after adding their synthetic mapping note,
  formula pointers, and coherent IDs. Private CI runs the canonical real-Vault
  test fail-closed. The real-ID/note-specific test is not copied into public
  CI, and there is no forked test suite.
- Local-Vault and published-snapshot compilation must produce byte-identical
  brief JSON. The comparison has no volatile brief fields, asserts that no
  absolute path occurs anywhere, and preserves `script.wpm_source` as an exact
  resolved payload value; the profile digest belongs in the manifest.
- The public/private boundary applies to every production consumer: after
  cutover only the publisher/builder reads the Vault. The backend `/hub` and
  `/hub/frame` routes are currently registered but dev-local-only by runtime
  guard; the target is to serve the hub from a published read model and frames
  from a separate media artifact store. The implementation may be split into
  a follow-up ticket, but T03 does not claim the Vault is gone until this
  consumer boundary is addressed.
- `/hub/frame` must receive an opaque `frame_id` or artifact reference, not a
  caller-controlled filesystem path. The existing anti-traversal guard remains
  required during migration, and dev/prod route exposure becomes an explicit
  build/config profile rather than an `is_dir()` surprise at runtime.
- Consumer checks remain limited to payload hash versus manifest, schema,
  internal consistency, and supported compatibility range. Publisher/private
  CI owns comparison with current SOT/taxonomy authorities and module digest.
  `freshness` is build-time state; current freshness, if needed, lives in a
  separate audited index keyed by `release_id`.

The Wayfinder destination is now sufficiently specified for `to-spec`. The
remaining work is implementation slicing: source adapters, synthetic mapping
fixtures and CI wiring, snapshot consumption, and the separate hub/media
artifact migration.

## Comments

### Round 1 — source, CI, and equivalence

- Source selection is mandatory and explicit. The current hard-coded Windows
  default in `brief_selfcheck.py` must not survive into the published path:
  missing or malformed source context fails with an actionable error rather
  than falling back to an author's Vault. The interface accepts an opaque
  source handle such as `local:<path>` or `release:<id>` and resolves it in an
  adapter; `VAULT_DIR` is authoring-only input to the local adapter.
- Source type must not appear in compiled brief output. The existing relative
  references and absence of timestamps/absolute paths are the desired shape.
- Public CI and trusted private CI share one parameterized test module. Public
  CI executes synthetic mapping fixtures; private CI executes the canonical
  real-Vault mapping test fail-closed. The real-ID/note-specific test is not
  placed in public CI, and the fixture mapping note, pointers, and coherent
  IDs must exist before the synthetic suite is enabled. No forked test file is
  allowed.
- The brief-equivalence criterion is byte-identical JSON with an explicit
  assertion that no absolute path occurs anywhere. There are no volatile brief
  fields; build metadata belongs in the release manifest, not the brief.
- `script.wpm_source` is the one provenance-bearing field requiring an explicit
  representation decision before implementation.

### Round 2 — one Vault reader and backend scope

- The boundary is global: after cutover, the Vault is readable only by the
  publisher/builder. The Analyzer compiler, production backend, workers, and
  public CI consume snapshots or published artifacts; they do not read the
  Vault directly.
- Local development compiles from a locally built draft snapshot through the
  same builder path. `VAULT_DIR` survives only inside that builder, not as a
  compiler/runtime fallback. Missing source context or a misspelled handle
  fails explicitly; hard-coded author-machine defaults are forbidden.
- The current backend `/hub` and `/hub/frame` endpoints are verified
  dev-local-only and absent from the production compose path, but they still
  read the mounted Vault. T03 must decide whether the cutover migrates them to
  a published snapshot/media artifact or explicitly defers them to a separate
  ticket without claiming that all Analyzer consumers are Vault-free.
