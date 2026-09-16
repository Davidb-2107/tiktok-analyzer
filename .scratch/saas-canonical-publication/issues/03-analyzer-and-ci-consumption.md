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
