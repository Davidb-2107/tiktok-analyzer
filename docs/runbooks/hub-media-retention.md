# Hub media retention runbook

The Analyzer operator owns the media artifact store mounted at `/hub/media`.
Keep artifacts for 30 days after their associated job is completed. Delete an
artifact only after that period, and only when it is not referenced by a
currently pinned release; a release reference takes precedence until that
release is retired.

The operator must include `/hub/media` in the host backup set and verify that a
backup can be restored before any cleanup. To restore, stop or drain the
Analyzer, restore the media directory from the latest known-good backup while
preserving opaque filenames, verify ownership and read-only mounting, then
start the service and check representative Hub frame URLs.

Operational procedure: review disk usage and pinned-release references weekly;
record cleanup and restore actions; remove only eligible artifacts with a
reversible backup available; escalate missing or corrupt referenced media
before deleting or republishing anything.
