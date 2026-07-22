---
name: extract-format
description: Use when the user wants to extract the reproducible FORMAT of a viral video or channel (style, camera, realism, action, hook mechanics — especially the first 3 seconds) — invoke as /extract-format <url> [url2 url3 ...]. Produces one comparable "format card" per video and, for multiple videos, a synthesized channel formula that can be reproduced.
requires:
  - python >= 3.8 (stdlib only, no pip install)
  - the sibling analyze-video skill (uses its analyze.py client)
  - network access to https://tiktok-analyzer.hen8n.com (or TT_BASE_URL override)
---

# extract-format

Reverse-engineer what a high-performing channel actually does: for each video,
fill a FIXED taxonomy (so cards are comparable across videos), with special
weight on the first 3 seconds — where the video wins or loses. With several
videos from the same channel, cross the cards to isolate the recurring,
reproducible formula.

## Invocation

```
/extract-format <video-url>
/extract-format <url1> <url2> <url3>     # channel mode: cards + synthesis
/extract-format <channel-url> [--top N]  # profile/channel page: top-N by views
```

## Step 0 — channel URL? Resolve to top videos first

If the argument is a channel/profile page (tiktok.com/@user without /video/,
youtube.com/@user or /channel/...), fetch its most-viewed videos:

```
GET <base>/channel/top?url=<channel-url>&n=<N, default 3>
```

Then run the per-video steps below on each returned `top[].url` and finish
with the channel synthesis. Mention each video's `views` in its card header —
ranking context matters for the formula.

## Steps (per video)

1. Fetch the hook window, densely sampled:
   ```
   python "<sibling analyze-video dir>/analyze.py" "<url>" --start 0 --end 3
   ```
2. Fetch the whole video (adaptive fps, hook OCR pass included). If a **niche**
   is in context (same condition as step 3), persist its frames + manifest by
   pointing `--out` at a stable per-video dir under the registry — gitignored,
   Syncthing-synced, never committed. If no niche is known, omit `--out` (fresh
   tempdir, cleaned up in step 6):
   ```
   # readable folder name "<channel> - <title>" (falls back to the video id
   # when a part is unknown). Pass --channel/--title ONLY when actually known —
   # channel mode's channel/top gives the title; single-video mode has neither.
   DIR=$(python "<vault root>/Projects/Sourcing/tools/frame_dir.py" "<url>" \
           --channel "<@handle>" --title "<title>")
   python "<sibling analyze-video dir>/analyze.py" "<url>" \
     --out "<vault root>/Projects/Sourcing/frames/<niche>/$DIR"
   ```
3. If this session has a **niche** in context — the video-project this analysis
   is for (e.g. Phase 0 research for a niche under `Projects/TikTok/<Name>`) —
   persist the verbatim transcript to the shared Sourcing registry. **Skip this
   step entirely if no niche is known** (e.g. standalone Sourcing exploration
   with no target project): never guess a niche, never write to an
   "uncategorized" bucket.
   ```
   python "<vault root>/Projects/Sourcing/tools/transcript_registry.py" <niche> <manifest.json from step 2> [--channel <@handle>] [--title <title>] [--views <N>]
   ```
   `--channel`/`--title`/`--views` are passed only when actually known (e.g.
   `--views`/`--title` come from Step 0's `channel/top` response in channel
   mode) — never invented. A "skip: already exists" message on stderr is
   expected and fine (dedup by video id, not an error).
4. `Read` ALL hook-window frames in order, then all full-video frames. The
   hook frames are the ground truth for the first-3-seconds section; the full
   frames for structure/style. Read the transcripts and overlay text from both
   manifests.
5. Fill the format card below. Every field, even if the answer is "none/NA" —
   missing fields make cards incomparable.
   **Archive it**: if a niche is in context (same condition as step 3), append
   the finished card verbatim to that video's registry file
   (`Projects/Sourcing/transcripts/<niche>/<video_id>.md`), after the existing
   sections, keeping the `## FORMAT CARD — ...` heading. This is what makes the
   card machine-readable later (`brief_compiler.py` parses the fixed taxonomy
   labels — a prose-only synthesis loses them). Skip if no niche is known.
6. Clean up scratch dirs (`rm -rf`) after the analysis is delivered — the
   hook-window tempdir (step 1), and the full-video tempdir (step 2) **only when
   no niche was in context**. NEVER delete a persisted
   `Projects/Sourcing/frames/<niche>/<dir>/` dir — keeping it is the point.

## Format card (fixed taxonomy — do not add/remove/rename fields)

```markdown
## FORMAT CARD — <@author> — <url>

### Hook (0–3s)
- **First frame shows:** <what is literally on screen at t=0>
- **On-screen text:** <hook overlay text, verbatim, or "none">
- **Spoken (0–3s):** <first words of transcript, or "none/music only">
- **Action:** <what happens in the first 3 seconds>
- **Cuts:** <number of distinct shots in 0–3s, from the dense frames>
- **Hook mechanic:** <one of: question | shock/pattern-interrupt | bold claim |
  mid-action start | curiosity gap | direct address | text-tease | other(describe)>

### Style
- **Video style:** <one of: talking head | POV skit | AI animation | screen
  recording | b-roll + voiceover | slideshow/photo | vlog | tutorial/demo |
  reaction | other(describe)>
- **Realism:** <1–5 scale: 1=fully realistic footage · 3=stylized/filtered ·
  5=fully cartoonish/animated> + one line why
- **Camera:** <static tripod | handheld | gimbal/tracking | screen capture |
  virtual/AI camera> · <framing: close-up / medium / wide> · <notable angle
  or movement, or "none">
- **Editing pace:** <avg seconds per shot across the video, rough> ·
  <captions style: karaoke word-by-word / block / none>

### Structure
- **Beats:** <timeline of the video's segments, e.g. "0–3 hook · 3–15 setup ·
  15–40 payoff list · 40–45 CTA". The last beat MUST quote the video's final
  sentence VERBATIM from the transcript — endings are where false "signature"
  devices get invented>
- **Sound:** <voiceover | on-camera speech | trending audio | music only> ·
  <music mood if any>
- **CTA:** <what the viewer is asked to do, or "none">

### Repro recipe
<3–6 imperative lines: exactly what to shoot/generate/write to clone this
format with a different topic. Concrete enough to hand to a producer.
Clone the SPREAD mechanics (hook, retention device, pacing) — NOT the
production polish. A well-shot video that doesn't spread has a bad format.>
```

## Channel mode (2+ URLs)

After producing every card, add a synthesis:

```markdown
## CHANNEL FORMULA — <@author>

- **Constant across videos:** <the fields with identical/near-identical values
  — this IS the format>
- **Variable slot(s):** <what changes per video — the "topic" dimensions>
- **Hook template:** <the recurring 0–3s pattern, as a fill-in-the-blank,
  e.g. "static close-up + text-tease '<bold claim>' + mid-action start">
- **Repro checklist:** <numbered, reproducible-every-time steps>
```

The formula only claims what at least ~2/3 of the cards support — call out
contradictions instead of averaging them away.

**Evidence rule for verbatim devices.** Any claimed constant that is a
word-for-word device (closing line, catchphrase, recurring overlay text) must
be proven by the exact quote from EACH video's transcript, cited in the
synthesis. Quotes that differ = NOT a constant — report the variation instead.
Never state a verbatim constant for a video whose transcript was not archived
(step 3). Incident 2026-07-22: an "and remember," truncated-closer was claimed
as a wisejourney constant with no transcript archived; re-verification showed
every top ends on a COMPLETE sentence — the false rule had already shipped
into a niche's script gate.

## Notes

- Engagement metrics (views/likes) are in each job's `script.txt` header via
  the API if ranking matters — but format extraction works without them.
- Cut counting at 2fps (the dense window default) undercounts very fast
  montages; say "≥N cuts (2fps floor)" when frames are all-different.
- Sibling skill path: this repo keeps skills in `skills/` and `.claude/skills/`;
  from `~/.claude/skills/extract-format/`, analyze.py is at
  `~/.claude/skills/analyze-video/analyze.py`.
- Vault root resolution: `<vault root>` is the Wiki_Claude vault directory
  (containing both `Projects/` and `Shared/`). If the agent is running from a
  niche-project session context, this path is already known; otherwise, ask the
  user for the vault root path rather than guessing.
