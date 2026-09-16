# Decide Analyzer and CI consumption

Status: open
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
