# T012 — Migrate legacy Vault records to declared channel identities

Status: open
Type: migration
Repository: Vault repository
Blocked by: T006

## Goal

Make the existing Vault consumable by the strict `channel_id` loader and the
private release gate without changing historical content or identity.

## Scope

- Add the frozen `channel_id` to every transcript in the selected publication
  scope, matching its parent channel partition.
- Add the same `channel_id` to each channel formula, matching its filename.
- Preserve current and historical handle text, card content, mapping notes,
  and handle-prefixed `subformula_id` values byte-for-byte apart from the
  explicit identity field additions.
- Validate the identity index and record the migration commit as the first
  publication-ready Vault revision.

## Acceptance criteria

- No selected transcript or formula lacks `channel_id` or disagrees with its
  partition/file identity.
- `format_card_registry.py --verify --niche neon_psycho` remains green and
  the canonical real-Vault mapping gate passes with `VAULT_DIR` set to this
  migrated Vault.
- The existing handles and sub-formula IDs remain unchanged; no FORMAT CARD,
  transcript prose, mapping assignment, or formula semantics are rewritten.
- The migration commit and exact validation commands are recorded for T009's
  publisher input.

## Out of scope

Publisher workflow, R2 publication, snapshot building, and Analyzer code are
owned by T009 and later tickets.
