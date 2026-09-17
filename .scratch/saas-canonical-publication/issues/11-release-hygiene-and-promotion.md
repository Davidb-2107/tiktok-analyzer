# T011 — Complete release hygiene and safe promotion

Status: resolved
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

Before the counter-tests, the Bucket Lock configuration was read directly from
the Cloudflare API (`GET /accounts/<account>/r2/buckets/snapshot-release/lock`).
The raw response exposed a leading space in the rule prefix:

```json
{
  "id": "immutable-releases",
  "enabled": true,
  "prefix": " releases/sha256/",
  "condition": {"type": "Indefinite"}
}
```

That prefix matched no published object. The rule was corrected through the
Cloudflare API with the exact prefix `releases/sha256/`, and a subsequent API
read confirmed the corrected value. No other rule field was changed.

## T011 counter-tests

The following six controls are distinct and have now been exercised against the
real R2 bucket. The workflow used `RELEASE_R2_WRITE_*` for PUT/DELETE and the
separate read credential for GET/read-back verification:

- [x] Bucket Lock rejects overwrite of an existing object below
  `releases/sha256/`.
- [x] Bucket Lock rejects deletion of that object.
- [x] A mutable index (`identity-index.json`, `freshness-index.json`, or
  `current.json`) remains writable outside the lock prefix.
- [x] The private gate rejects an absent `release_id`.
- [x] The private gate rejects a payload whose bytes are altered while the
  manifest remains unchanged.
- [x] The private gate rejects an altered manifest whose release identity or
  payload digest no longer matches the pinned release.

Evidence from the green counter-test run:

- [counter-test workflow](https://github.com/Davidb-2107/Wiki_Claude/actions/runs/35256990816)
  - existing overwrite: refused with HTTP `409`;
  - existing delete: refused with HTTP `409`;
  - new-object overwrite: refused with HTTP `409`;
  - new-object delete: refused with HTTP `409`;
  - mutable `current.json`: update accepted and restored;
  - altered payload: private gate refused it;
  - altered manifest: private gate refused it;
  - workflow result: `T011 R2 counter-tests ... OK`.
- [absent release gate](https://github.com/Davidb-2107/Wiki_Claude/actions/runs/35246330014)
  - `sha256:` followed by 64 zeroes was rejected with
    `ERROR: release is unavailable`.
- [post-fix positive gate](https://github.com/Davidb-2107/Wiki_Claude/actions/runs/35257152447)
  - the real release `sha256:262e90930dbae113339a5933d0f905294ba1ec9b5bdb3ee82dd1857663ddd939`
    passed the private mapping suite.

The old and new object probes both being refused demonstrates that the fixed
lock applies to existing and newly uploaded objects in the effective
`releases/sha256/` namespace. All T011 acceptance criteria are satisfied and
the evidence is recorded. Any remaining merge or production decision is a
separate release-process decision, outside T011 acceptance.

## Out of scope

Merging, deleting branches, changing the default branch, and SaaS production
deployment require a separate explicit decision.
