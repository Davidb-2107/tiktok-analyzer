# Deterministic Sub-formula Mapping Contract

Status: approved for design on 2026-09-15. No `--cluster` implementation is
included in this decision.

## Goal

Represent several reproducible content formulas inside one channel without
letting the Analyzer invent formulas from visual similarity or majority votes.
The human-audited mapping is the business truth; future code only applies it.

## Vocabulary

- **Channel Formula**: the reference envelope for one channel, including its
  recurring visual and production characteristics.
- **Sub-formula**: a reproducible content recipe inside one Channel Formula,
  defined by a shared hook, angle/promise, narrative progression, and payoff.
- **Visual style**: observed rendering characteristics such as `Video style`,
  `Realism`, palette, camera, and assets. It does not define a sub-formula.
- **Outlier**: an explicitly mapped video that is retained for analysis but is
  not eligible to create or select a production formula.

## Source of truth

The canonical mapping is the reviewed table in the Vault note:

`wiki/analyses/2026-09-11-neon-psycho-clusters.md`

There is no second inferred mapping. A future implementation may use a
machine-readable representation of this same mapping, but it must preserve the
same human-approved assignments and never regenerate them from card statistics.

Each channel formula that participates in clustering will expose a stable
pointer to this note, for example:

```yaml
subformula_mapping_ref: wiki/analyses/2026-09-11-neon-psycho-clusters.md
```

The pointer is only a reference; it does not duplicate the assignments. The
Analyzer must follow the pointer for the already selected channel and must not
discover mapping notes by date, filename glob, or majority statistics.

For the first implementation, the canonical representation is the exact
Markdown table under `## Décision — mapping canonique vidéo → sous-formula`.
Only rows from that table are data; surrounding prose is explanatory. A future
structured representation requires an explicit migration of this contract.

## Mapping contract

Each sourced video has exactly one mapping record within its `(niche, channel)`
scope:

```text
(niche, channel, video_id) -> subformula_id | outlier
```

Rules:

1. `channel` is mandatory, canonical, and part of the identity. A sub-formula
   cannot combine videos from different channels.
2. `subformula_id` is channel-scoped and should include the channel identity
   when serialized, as in `viraldtoprw_end_of_life_attachment`.
3. A sub-formula requires at least two videos in the current audit and must be
   justified by shared content mechanics: hook, angle/promise, progression, and
   payoff. `Hook mechanic` alone is insufficient.
4. `Video style`, `Realism`, palette, camera, and assets remain descriptive
   evidence. Equal values across channels must never merge their formulas.
5. An outlier remains addressable by video ID but cannot be selected as a
   production formula or used to create a new formula by itself.
6. New cards do not receive an automatic assignment. They require an explicit
   mapping decision and review.

## Approved `neon_psycho` mapping

### `@viraldtoprw`

- `viraldtoprw_end_of_life_attachment`:
  `7571154788486827295`, `7568334048544820510`.
- `viraldtoprw_behavioral_attachment`:
  `7572606346403564831`, `7570326672780643614`, `7572554313268989215`.

Both groups have a single `Hook mechanic` within the subgroup (`bold claim`
2/2 and `question` 3/3) and share a coherent content progression.

### `@the.wisejourney`

- `wise_provocative_relationship_claim`:
  `7597962877495938326`, `7604187243971939606`.
- `wise_pattern_interrupt_shock`:
  `7608722463937072407`, `7629453809315499286`, retained as an
  `analysis_group_only` mapping because the two content angles and payoffs are
  not homogeneous enough for a production formula.
- `7589746128195783958`: `outlier`.

## Future `--cluster` behavior

The future command operates only after a channel has been selected. It applies
the approved mapping and must:

- return only the sub-formula covering the requested video IDs;
- reject missing, duplicated, unknown, or cross-channel mapping records;
- keep outliers explicitly unassigned rather than falling back to a guessed
  formula;
- reject `analysis_group_only` as a production formula;
- never use a majority vote over `Video style`, `Realism`, or `Hook mechanic`
  as a substitute for the mapping.

## Acceptance criteria for implementation

- The two `@viraldtoprw` mappings resolve to disjoint, exact ID sets.
- `@the.wisejourney` resolves its relationship-claim group, preserves the
  shock group as analysis-only, and leaves the question video as an outlier.
- A brief for one channel never inherits a style, hook, Realism value, card
  reference, or formula reference from the other channel.
- Invalid mappings fail explicitly and do not silently select a partial formula.
- Existing FORMAT CARD text remains byte-for-byte unchanged.

## Non-goals

- Automatic clustering or semantic discovery.
- Rewriting FORMAT CARDs to force convergence.
- Changing the `Realism` scale.
- Resolving `dark_psycho`, Stickman dates, voice calibration, or engine gates.
