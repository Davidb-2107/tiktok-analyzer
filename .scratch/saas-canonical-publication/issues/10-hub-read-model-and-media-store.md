# T010 — Migrate Hub reads and frames off the Vault

Status: resolved
Type: implementation
Repository: `tiktok-analyzer-format-cards`
Blocked by: T007, T009

## Goal

Make `/hub` consume a deterministic projection of the pinned snapshot runtime
and make frame access use opaque media artifact IDs instead of Vault paths.

## Files

- Create `backend/hub_read_model.py`.
- Create `backend/media_store.py`.
- Modify `backend/main.py` and `backend/hub.py`.
- Modify `backend/test_hub.py`.
- Modify `docker-compose.yml`, `docker-compose.prod.yml`, and the relevant
  container configuration.

## Acceptance criteria

- Production `/hub` reads the projection for the configured pinned release and
  never mounts or discovers the Vault.
- The projection is derived from snapshot `runtime`, carries the same
  `release_id`, and has no independent publication or retention authority.
- `/hub/frame/{frame_id}` accepts an opaque artifact ID only; callers cannot
  supply filesystem paths.
- Frames are stored outside the text snapshot with a separately documented
  retention policy.
- Production route exposure is controlled by build/configuration profile;
  `is_dir()` is not the production feature flag.
- Tests prove old handle provenance does not alter channel routing and that
  traversal/path-shaped frame input is rejected.
- Local development can use the explicit draft source context without
  reintroducing a machine-specific default.

## Answer

T010 keeps the opaque `frame_id` plumbing and the separate media store, but
Hub thumbnails are officially not served yet. No producer currently populates
`HUB_MEDIA_ROOT`, and runtime cards do not publish `frame_id`, so the Hub
returns no thumbnail until a media artifact is actually available.

A follow-up ticket must define the producer, frame-ID assignment rule, and
R2-to-media-store synchronization (or replace the filesystem adapter with an
object-store adapter). T010 does not invent that producer.

The dev-only `transcript_registry` bridge in `backend/main.py` is a separate
retirement item and remains open in the audit ledger; it is outside T010.

## Out of scope

Media-provider selection and SaaS authorization policy are separate design
decisions; this ticket only enforces the published artifact boundary.
