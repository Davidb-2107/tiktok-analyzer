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

The public Analyzer PR and the Vault `snapshot-contract` are green. Vault PR
#20 was merged into `master` at `05cb8bad27981507ae247345dc92ca374f719969`;
the Analyzer promotion PR remains separate and unmerged.

The first real private publication and gate have now run on
`codex/channel-scoped-sourcing`:

- publication run:
  https://github.com/Davidb-2107/Wiki_Claude/actions/runs/35230212912
- private gate run:
  https://github.com/Davidb-2107/Wiki_Claude/actions/runs/35230373092
- Vault commit: `3bcb8b690b52267e91b5816937c5d3b06c71a98a`
- Analyzer contract pin: `270a979f11581d1d8046a21f0d68f43441a70f9a`
- published release: `sha256:262e90930dbae113339a5933d0f905294ba1ec9b5bdb3ee82dd1857663ddd939`
- private mapping suite: `61` tests, `OK`

This proves the builder → R2 → authenticated read → release materialization →
private mapping path for a real release. T011 remains open until the remote
Bucket Lock and negative gate controls below are exercised and recorded.

## T011 counter-tests

The following six controls are distinct and must each have a recorded result:

- [ ] Bucket Lock rejects overwrite of an existing object below
  `releases/sha256/`.
- [ ] Bucket Lock rejects deletion of that object.
- [ ] A mutable index (`identity-index.json`, `freshness-index.json`, or
  `current.json`) remains writable outside the lock prefix.
- [ ] The private gate rejects an absent `release_id`.
- [ ] The private gate rejects a payload whose bytes are altered while the
  manifest remains unchanged.
- [ ] The private gate rejects an altered manifest whose release identity or
  payload digest no longer matches the pinned release.

Cloudflare documents that Bucket Lock rules apply to both new and existing
objects. The release above is therefore in scope when the
`releases/sha256/` rule is enabled, but remote enforcement still requires the
negative tests above:
https://developers.cloudflare.com/r2/buckets/bucket-locks/

## Out of scope

Merging, deleting branches, changing the default branch, and SaaS production
deployment require a separate explicit decision.
