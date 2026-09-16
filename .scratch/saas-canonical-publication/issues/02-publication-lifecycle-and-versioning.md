# Decide publication lifecycle and versioning

Status: open
Type: grilling
Blocked by: none (01 resolved)

## Question

How does an approved Vault state become a published canonical snapshot, and how
are validation, ownership, versioning, rollback, and provenance enforced?

The decision must define the publisher, required gates, immutable versus mutable
records, handling of rejected or incomplete source data, and how a release can
be reproduced without access to the author's local Vault path.

The publication gate must carry the resolved taxonomy semantic version together
with the digest of the authoritative taxonomy module. Matching value arrays
alone are insufficient because the Vault and CI modules can have different
behavior.

The decision must also define the version rule: the taxonomy version is a
monotone semantic version owned by the taxonomy authority, it is bumped for
any allowed-value or validation-behavior change, and every published snapshot
stores the authoritative module digest alongside it. The digest is the
behavioral anchor; the version is the human-readable compatibility signal.
