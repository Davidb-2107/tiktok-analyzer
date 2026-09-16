# Deterministic Sub-formula Mapping — Release Note

Analyzer sub-formula routing is deterministic and mapping-driven. A selected
channel follows its declared Vault mapping reference and returns only the
approved video IDs for that channel; card and formula references remain
channel-scoped.

Release verification requires an explicit real `VAULT_DIR`. The canonical gate
fails closed if the Vault, mapping note, or formula reference is unavailable,
and verifies `outlier` and `analysis_group_only` remain non-production states.

Known limits: no automatic clustering or similarity-based grouping, no automatic
assignment for new cards, and no change to FORMAT CARDs, transcripts, Realism,
voice, engines, Stickman, or `dark_psycho`.
