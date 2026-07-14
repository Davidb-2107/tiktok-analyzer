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
2. Fetch the whole video (adaptive fps, hook OCR pass included):
   ```
   python "<sibling analyze-video dir>/analyze.py" "<url>"
   ```
3. `Read` ALL hook-window frames in order, then all full-video frames. The
   hook frames are the ground truth for the first-3-seconds section; the full
   frames for structure/style. Read the transcripts and overlay text from both
   manifests.
4. Fill the format card below. Every field, even if the answer is "none/NA" —
   missing fields make cards incomparable.
5. Clean up scratch dirs (`rm -rf`) after the analysis is delivered.

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
  15–40 payoff list · 40–45 CTA">
- **Sound:** <voiceover | on-camera speech | trending audio | music only> ·
  <music mood if any>
- **CTA:** <what the viewer is asked to do, or "none">

### Repro recipe
<3–6 imperative lines: exactly what to shoot/generate/write to clone this
format with a different topic. Concrete enough to hand to a producer.>
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

## Notes

- Engagement metrics (views/likes) are in each job's `script.txt` header via
  the API if ranking matters — but format extraction works without them.
- Cut counting at 2fps (the dense window default) undercounts very fast
  montages; say "≥N cuts (2fps floor)" when frames are all-different.
- Sibling skill path: this repo keeps skills in `skills/` and `.claude/skills/`;
  from `~/.claude/skills/extract-format/`, analyze.py is at
  `~/.claude/skills/analyze-video/analyze.py`.
