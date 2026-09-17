# T011 — Complete release hygiene and safe promotion

Status: open
Type: release-readiness
Repository: `tiktok-analyzer-format-cards`
Blocked by: T008, T009, T010

## Goal

Remove the known publication hazards, verify the real PR path, and promote
the feature branch without accidentally pushing to `origin/master`.

## Files

- Modify `.superpowers/sdd/2026-09-15-analyzer-real-vault-smoke/task-1-report.md`
  to remove local absolute paths.
- Modify `.superpowers/sdd/2026-09-15-deterministic-subformula-mapping-t002/task-2-report.md`
  to remove local absolute paths.
- Update the release checklist in
  `docs/superpowers/plans/2026-09-16-saas-canonical-publication.md` with the
  verified promotion command.

## Acceptance criteria

- No versioned report contains an absolute Windows path, a Codex runtime path,
  or another author-machine path.
- `git diff --check` and the full relevant test suites pass.
- The branch upstream is inspected explicitly; promotion uses
  `git push origin HEAD:refs/heads/codex/channel-scoped-sourcing` rather than
  a bare `git push`.
- A pull request targets `master` so the Analyzer CI actually runs.
- The public mapping job is green.
- After T009 has produced a real immutable release, the trusted private gate
  is dispatched with that pinned `release_id`; its evidence is recorded and no
  claim says that public CI validated the private snapshot.
- The final worktrees are clean and the exact pushed commit SHAs are recorded.

## T011 resolution

The public Analyzer PR and the Vault `snapshot-contract` are green. The
trusted private gate is intentionally not claimed: its environment, release
source URL, read credential, and real pinned `release_id` do not exist yet.
The first private run is pending creation of the immutable release registry;
until then, T011 is technically promoted but infrastructure-blocked on its
third acceptance criterion.

The pull requests remain open and `master` is unchanged. Merging is a separate
explicit release-process decision, outside T011 acceptance: “technically
promoted” means pushed, pinned, and CI-validated, not merged or in production.

## Out of scope

Merging, deleting branches, changing the default branch, and SaaS production
deployment require a separate explicit decision.
