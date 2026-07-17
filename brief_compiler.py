"""Compilateur format_card -> brief.json.

Prend les artefacts d'extract-format d'une niche (registre Sourcing : transcripts
+ CHANNEL FORMULA) et compile un brief exécutable qui VALIDE contre
brief.schema.json. Aucune constante de prod locale :
  - durées/pacing importés de Shared/tiktok-spec/tiktok_duration.py (SOT)
  - provenance moteur lue dans Shared/ENGINE-FACTS.md (assert si absente)
  - WPM lu du profil voix calibré Shared/voice-calibration/voice_wpm.json
    (TODO explicite si aucun profil — jamais deviné)

Usage :  python brief_compiler.py <niche> [--voice ALIAS] [--language fr]
                                  [--out brief_<niche>.json]
Self-check : python test_brief_compiler.py
"""

import argparse
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

import brief_selfcheck as sc  # VAULT, load_sot, validate_* — le contrat existant

HERE = Path(__file__).resolve().parent
TRANSCRIPTS = sc.VAULT / "Projects" / "Sourcing" / "transcripts"
FORMATS = sc.VAULT / "Projects" / "Sourcing" / "formats"
FRAMES = sc.VAULT / "Projects" / "Sourcing" / "frames"
ENGINE_FACTS = sc.VAULT / "Shared" / "ENGINE-FACTS.md"
VOICE_CAL = sc.VAULT / "Shared" / "voice-calibration"


# --- parsing registre ---------------------------------------------------------
def parse_frontmatter(text):
    """Frontmatter YAML plat -> (dict, body). ponytail: parser ligne à ligne
    key: value (le registre n'écrit que du YAML plat), pas de lib yaml."""
    if not text.startswith("---"):
        return {}, text
    end = text.index("\n---", 3)
    meta = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line.strip())
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip().strip('"')
        meta[k] = int(v) if v.isdigit() else v
    return meta, text[end + 4 :]


def load_registry(niche):
    """Toutes les vidéos du registre de la niche (frontmatter + transcript)."""
    d = TRANSCRIPTS / niche
    assert d.is_dir(), f"registre introuvable: {d}"
    videos = []
    for f in sorted(d.glob("*.md")):
        meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        if "video_url" not in meta:  # fichier non-registre (AGENTS.md, notes...)
            continue
        m = re.search(r"## Transcript.*?\n\n(.+?)(?:\n\n## |\Z)", body, re.S)
        videos.append(
            {
                "video_id": f.stem,
                "url": meta.get("video_url", ""),
                "channel": meta.get("channel", ""),
                "title": meta.get("title", ""),
                "views": meta.get("views", 0),
                "transcript": (m.group(1).strip() if m else ""),
                "ref": f"Projects/Sourcing/transcripts/{niche}/{f.name}",
            }
        )
    assert videos, f"registre vide: {d}"
    return videos


def find_formula(videos):
    """Retrouve la CHANNEL FORMULA du registre : le fichier formats/*.md dont le
    frontmatter `videos:` recoupe les URLs de la niche."""
    ids = {v["video_id"] for v in videos}
    for f in sorted(FORMATS.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        if any(vid in text for vid in ids):
            return f, text
    return None, None


# --- formula -> champs format -------------------------------------------------
def _slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.split(r"[:(—-]| - ", s, 1)[0]  # coupe à ':', '(', tiret long
    words = re.findall(r"[a-z0-9]+", s.lower())
    return "_".join(
        w
        for w in words
        if w not in ("l", "le", "la", "les", "d", "de", "du", "un", "une")
    )[:40]


def _section(text, title):
    """Contenu d'une section '## <title>...' jusqu'au prochain '## '."""
    m = re.search(rf"^## {title}.*?\n(.*?)(?=^## |\Z)", text, re.S | re.M | re.I)
    return m.group(1).strip() if m else ""


def _bullets(block):
    items, cur = [], None
    for line in block.splitlines():
        if re.match(r"^\s*(?:[-*]|\d+\.)\s+", line):
            if cur:
                items.append(cur)
            cur = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line).strip()
        elif cur and line.strip():
            cur += " " + line.strip()
    if cur:
        items.append(cur)
    return items


# ponytail: mapping mots-clés formula -> taxonomie ; suffit tant que la formula
# est de la prose. Si extract-format archive les cards taxonomiques brutes,
# parser les labels **Video style:** / **Realism:** / **Hook mechanic:** direct.
STYLE_KEYWORDS = [
    (r"wireframe|hologram|anim|IA|AI ", "AI animation", 5),
    (r"talking head|face cam", "talking head", 1),
    (r"b-?roll", "b-roll + voiceover", 2),
]
HOOK_KEYWORDS = [
    (r"\bquestion\b", "question"),
    (r"bold claim|affirmation", "bold claim"),
    (r"text-?tease", "text-tease"),
    (r"mid-?action", "mid-action start"),
    (r"curiosity", "curiosity gap"),
]


def derive_format(formula_text):
    style, realism = "other", 3
    for pat, s, r in STYLE_KEYWORDS:
        if re.search(pat, formula_text, re.I):
            style, realism = s, r
            break
    hook_mechanic = "other"
    for pat, h in HOOK_KEYWORDS:
        if re.search(pat, formula_text, re.I):
            hook_mechanic = h
            break

    constant = {}
    for item in _bullets(_section(formula_text, r"Constant")):
        m = re.match(r"\*\*(.+?)\*\*\s*:?\s*(.*)", item)
        key = _slug(m.group(1)) if m else _slug(item)
        constant[key or f"c{len(constant)}"] = (m.group(2) if m else item).strip()

    slots = [_slug(b) for b in _bullets(_section(formula_text, r"Slots variables"))]
    slots = [s for s in slots if s] or ["topic"]

    hook_block = _section(formula_text, r"Hook template")
    m = re.search(r"```\n(.*?)```", hook_block, re.S)
    hook_template = " ".join((m.group(1) if m else hook_block).split()) or "TODO"

    repro = _bullets(_section(formula_text, r"Repro checklist"))
    if repro:
        constant["repro_checklist"] = repro
    return style, realism, hook_mechanic, hook_template, constant, slots


# --- SOT voix -----------------------------------------------------------------
def load_voice(niche, alias, language):
    """(voice_id, wpm, source). Profil calibré uniquement — sinon TODO explicite."""
    sys.path.insert(0, str(VOICE_CAL))
    try:
        import voice_wpm
    except ImportError:
        return (
            "TODO(calibrate-voice)",
            200.0,
            "TODO: module voice_wpm non importable — lancer calibrate-voice",
        )

    data = json.loads((VOICE_CAL / "voice_wpm.json").read_text(encoding="utf-8"))
    if not alias:
        key = re.sub(r"[^a-z0-9]", "", niche.lower())
        cands = [
            k
            for k in data
            if not k.startswith("_")
            and re.sub(r"[^a-z0-9]", "", k.lower()).startswith(key)
        ]
        if not cands:
            return (
                "TODO(calibrate-voice)",
                float(data.get("_default", 200)),
                f"TODO: aucun profil voix pour la niche '{niche}' — lancer calibrate-voice (valeur _default non calibrée)",
            )
        # ponytail: défaut = alias le plus utilisé en prod (runs), tiebreak nom court
        alias = max(
            cands, key=lambda k: (len(data[k].get("observed_runs", [])), -len(k))
        )

    wpm, label = voice_wpm.get_wpm(alias, language=language)
    profile = voice_wpm.get_profile(alias, language=language) or {}
    voice_id = profile.get("voice_id", f"TODO(profil {alias} sans voice_id)")
    return voice_id, wpm, f"voice_wpm.json '{alias}' lang={language}: {label}"


# --- SOT moteurs --------------------------------------------------------------
def engine_provenance(niche):
    """(kling_line, seedance_line) — lues d'ENGINE-FACTS, assert si absentes."""
    text = ENGINE_FACTS.read_text(encoding="utf-8")
    kling = next(
        (
            ln.strip("- ").strip()
            for ln in text.splitlines()
            if re.search(rf"défaut {niche}", ln, re.I)
        ),
        None,
    )
    kling = kling or next(
        (
            ln.strip("- ").strip()
            for ln in text.splitlines()
            if "kling3_0" in ln and "std" in ln
        ),
        None,
    )
    seedance = next(
        (
            ln.strip("- ").strip()
            for ln in text.splitlines()
            if re.search(r"hero shots", ln, re.I)
        ),
        None,
    )
    assert kling and seedance, (
        "faits kling3_0/Seedance absents d'ENGINE-FACTS — vérifier avant de compiler"
    )
    fmt = lambda ln: f"ENGINE-FACTS (Shared/ENGINE-FACTS.md): {ln[:160]}"
    return fmt(kling), fmt(seedance)


# --- beats + shots ------------------------------------------------------------
def build_beats(target_s, wpm, hook_template, constant):
    """Squelette de beats vers le milieu de la fenêtre SOT, budget mots par beat.
    ponytail: split fixe hook 3s / setup 25% / payoff reste (+ cta 2.5s si le
    format en a un en constant) — affiner par niche quand un vrai pattern émerge."""
    total = round(sum(target_s) / 2, 1)
    words = lambda d: int(round(wpm * d / 60))
    has_cta = any("cta" in k for k in constant)
    cta_d = 2.5 if has_cta else 0.0
    body_end = total - cta_d
    setup_end = round(3.0 + 0.25 * (body_end - 3.0), 1)
    beats = [
        {
            "id": "hook",
            "role": "hook",
            "t_start": 0.0,
            "t_end": 3.0,
            "text": f"<hook, ~{words(3.0)} mots> template: {hook_template}",
        },
        {
            "id": "setup",
            "role": "setup",
            "t_start": 3.0,
            "t_end": setup_end,
            "text": f"<setup du <topic>, ~{words(setup_end - 3.0)} mots — poser le contexte, vocabulaire du format>",
        },
        {
            "id": "payoff",
            "role": "payoff",
            "t_start": setup_end,
            "t_end": body_end,
            "text": f"<payoff, ~{words(body_end - setup_end)} mots — dérouler la structure du format jusqu'à la clôture émotionnelle>",
        },
    ]
    if has_cta:
        beats.append(
            {
                "id": "cta",
                "role": "cta",
                "t_start": body_end,
                "t_end": total,
                "text": f"<cta, ~{words(cta_d)} mots> {constant.get('cta', '')}".strip(),
            }
        )
    return beats


def build_shots(beats, shot_s):
    lo, hi = shot_s
    pace = round((lo + hi) / 2, 2)
    shots, n = [], 0
    for b in beats:
        dur = b["t_end"] - b["t_start"]
        # round (pas ceil) : un beat court reste UN plan (formula: hook sans coupe)
        k = max(1, round(dur / pace))
        while dur / k > hi:
            k += 1
        d = round(dur / k, 2)
        for i in range(k):
            n += 1
            shots.append(
                {
                    "id": f"s{n}",
                    "beat": b["id"],
                    "duration_s": max(lo, d),
                    "prompt_ref": "p_hero" if n == 1 else "p_body",
                    "motion": "ken_burns_in" if i % 2 == 0 else "ken_burns_out",
                }
            )
    return shots


# --- compilation --------------------------------------------------------------
def compile_brief(niche, voice=None, language="fr"):
    target_s, shot_s = sc.load_sot()
    videos = load_registry(niche)
    formula_path, formula_text = find_formula(videos)
    assert formula_text, (
        f"CHANNEL FORMULA introuvable dans {FORMATS} pour la niche {niche}"
    )

    style, realism, hook_mechanic, hook_template, constant, slots = derive_format(
        formula_text
    )
    frames_dir = FRAMES / niche
    if frames_dir.is_dir():
        constant["frames_ref"] = f"Projects/Sourcing/frames/{niche}/"

    voice_id, wpm, wpm_source = load_voice(niche, voice, language)
    kling_prov, seedance_prov = engine_provenance(niche)

    beats = build_beats(target_s, wpm, hook_template, constant)
    shots = build_shots(beats, shot_s)

    camera = constant.get("camera", constant.get("cameras", ""))
    style_line = next(iter(constant.values())) if constant else style
    brief = {
        "schema_version": "0.1",
        "niche": niche,
        "source": {
            "videos": [
                {k: v[k] for k in ("url", "video_id", "channel", "title", "views")}
                for v in videos
            ],
            "format_card_ref": videos[0]["ref"].rsplit("/", 1)[0] + "/",
            "channel_formula_ref": str(formula_path.relative_to(sc.VAULT)).replace(
                "\\", "/"
            ),
        },
        "format": {
            "style": style,
            "realism": realism,
            "hook_mechanic": hook_mechanic,
            "hook_template": hook_template,
            "constant": constant,
            "variable_slots": slots,
        },
        "script": {
            "language": language,
            "voice_id": voice_id,
            "target_wpm": wpm,
            "wpm_source": wpm_source,
            "beats": beats,
        },
        "shots": shots,
        "prompt_pack": [
            {
                "id": "p_hero",
                "engine": "seedance",
                "mode": "pro",
                "sound": "off",
                "prompt": f"hero shot (hook 0-3s): {style_line} — {camera or 'plan fixe / drift lent'} — <topic>",
                "provenance": seedance_prov,
            },
            {
                "id": "p_body",
                "engine": "kling3_0",
                "mode": "std",
                "sound": "off",
                "prompt": f"{style_line} — {camera or 'plan fixe / drift lent'} — beat courant du script, <topic>",
                "provenance": kling_prov,
            },
        ],
        "captions": {"style": "karaoke", "max_lines": 1, "preset": "CC-DerStil"},
        "gates": {
            "target_duration_s": target_s,
            "shot_duration_s": shot_s,
            "aspect_ratio": "9:16",
            "source": "Shared/tiktok-spec/tiktok_duration.py",
            "checks": [
                "durée finale dans target_duration_s",
                "chaque shot dans shot_duration_s",
                "9:16",
                "captions <=1 ligne",
                "silences coupés",
            ],
        },
    }
    # ASSERT avant écriture : le brief valide contre le contrat existant.
    sc.validate_structure(brief)
    sc.validate_against_sot(brief, target_s, shot_s)
    return brief


def main():
    ap = argparse.ArgumentParser(description="Compile format_card -> brief.json")
    ap.add_argument("niche")
    ap.add_argument("--voice", help="alias voice_wpm.json (défaut: auto par niche)")
    ap.add_argument("--language", default="fr")
    ap.add_argument("--out")
    args = ap.parse_args()

    brief = compile_brief(args.niche, voice=args.voice, language=args.language)
    out = Path(args.out) if args.out else HERE / f"brief_{args.niche}.json"
    out.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK — brief valide ecrit: {out}")
    print(
        f"  beats: {len(brief['script']['beats'])}  shots: {len(brief['shots'])}  "
        f"wpm: {brief['script']['target_wpm']}  voice: {brief['script']['voice_id']}"
    )


if __name__ == "__main__":
    main()
