"""Compilateur format_card -> brief.json.

Prend les artefacts d'extract-format d'une niche (registre Sourcing : transcripts
+ CHANNEL FORMULA) et compile un brief exécutable qui VALIDE contre
brief.schema.json. Aucune constante de prod locale :
  - durées/pacing importés de Shared/tiktok-spec/tiktok_duration.py (SOT)
  - provenance moteur lue dans Shared/ENGINE-FACTS.md (TODO explicite si aucun
    verdict par-niche — jamais deviné)
  - WPM lu du profil voix calibré Shared/voice-calibration/voice_wpm.json
    (TODO explicite si aucun profil — jamais deviné)
  - taxonomie (style/realism/hook_mechanic) lue des FORMAT CARDs archivées dans
    les fichiers registre par-vidéo quand elles existent ; sinon inférence
    mots-clés sur la prose de la formula (fallback)

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
from collections import Counter
from pathlib import Path

import brief_selfcheck as sc  # VAULT, load_sot, validate_* — le contrat existant

HERE = Path(__file__).resolve().parent
TRANSCRIPTS = sc.VAULT / "Projects" / "Sourcing" / "transcripts"
FORMATS = sc.VAULT / "Projects" / "Sourcing" / "formats"
FRAMES = sc.VAULT / "Projects" / "Sourcing" / "frames"
ENGINE_FACTS = sc.VAULT / "Shared" / "ENGINE-FACTS.md"
VOICE_CAL = sc.VAULT / "Shared" / "voice-calibration"

# taxonomie STYLES/MECHANICS/REALISM_VALUES + parse_card/inspect_file : SOT
# partagée (Task 1) — pas de copie locale, pas de deuxième regex bornée.
FCR_TOOLS = sc.VAULT / "Projects" / "Sourcing" / "tools"
FCR_MODULE = FCR_TOOLS / "format_card_registry.py"
if not FCR_MODULE.is_file():
    raise ModuleNotFoundError(
        "Validateur FORMAT CARD introuvable : module attendu ici "
        f"{FCR_MODULE} (vault configuré : {sc.VAULT}). "
        "La validation des cards ne peut pas continuer ; vérifiez que le module "
        "du vault Projects/Sourcing/tools est présent."
    )
sys.path.insert(0, str(FCR_TOOLS))
try:
    import format_card_registry as fcr
except ImportError as exc:
    raise ImportError(
        "Impossible d'importer le validateur FORMAT CARD du vault. "
        f"Chemin attendu : {FCR_MODULE} ; contexte : brief_compiler.py "
        "en dépend pour inspecter et valider les cards, sans fallback silencieux."
    ) from exc


# --- parsing registre ---------------------------------------------------------
def parse_frontmatter(text):
    """Frontmatter YAML plat -> (dict, body). ponytail: parser ligne à ligne
    key: value (le registre n'écrit que du YAML plat), pas de lib yaml."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:  # frontmatter non fermé (fichier fraîchement ingéré) -> pas de crash
        return {}, text
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
        m = re.search(r"## Transcript.*?\n\n(.+?)(?:\n\n## |\Z)", body, re.DOTALL)
        videos.append(
            {
                "video_id": f.stem,
                "url": meta.get("video_url", ""),
                "channel": meta.get("channel", ""),
                "title": meta.get("title", ""),
                "views": meta.get("views", 0),
                "transcript": (m.group(1).strip() if m else ""),
                # card taxonomique archivée par extract-format (step 5) : on a déjà
                # le chemin du fichier ici -> fcr.inspect_file(f) (surface publique
                # du module partagé, Task 1 ; lit et borne elle-même l'extraction,
                # jamais jusqu'à EOF) plutôt qu'une regex bornée en double sur `body`
                # déjà lu, ou le finder privé fcr._find_card_section. Rend déjà
                # n_sections/valid/errors/card (fields) -> inspect_cards() n'a plus
                # besoin de reparser le texte via fcr.parse_card en double.
                "card_inspect": fcr.inspect_file(f),
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
    m = re.search(
        rf"^## {title}.*?\n(.*?)(?=^## |\Z)",
        text,
        re.DOTALL | re.MULTILINE | re.IGNORECASE,
    )
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


# Taxonomie fixe d'extract-format (STYLES/MECHANICS/REALISM_VALUES) : plus de
# copie locale ici, elle vit dans fcr (module partagé, Task 1) et fcr.parse_card
# valide déjà les 3 champs contre elle.


def _inspect_one(v):
    """fcr.inspect_file()-shaped dict ({"n_sections","valid","errors","card"})
    avec ``format_card_status`` explicite (None pour les fixtures textuelles
    sans statut). Un statut source non nul peut signaler un blocage qui ne doit
    pas être confondu avec une card manquante.
    pour une vidéo. Préfère "card_inspect", déjà calculé par load_registry via
    la surface publique fcr.inspect_file(f) (pas de deuxième parse). Fallback
    pour la forme de test synthétique {"card": <texte>} : parse à la demande
    via fcr.parse_card, seule voie encore publique sur du texte déjà en main."""
    inspected = v.get("card_inspect")
    if inspected is not None:
        return {**inspected, "format_card_status": inspected.get("format_card_status")}
    text = v.get("card", "")
    if not text:
        return {
            "n_sections": 0,
            "valid": False,
            "errors": ["no FORMAT CARD section found"],
            "card": None,
            "format_card_status": None,
        }
    card = fcr.parse_card(text)
    return {
        "n_sections": 1,
        "valid": card["valid"],
        "errors": card["errors"],
        "card": card,
        "format_card_status": None,
    }


def inspect_cards(videos):
    """Card coverage + validity report pour une niche.

    Chaque vidéo (issue de `load_registry`) porte déjà "card_inspect" (le
    dict retourné par fcr.inspect_file()). N'appelle fcr.parse_card qu'une
    fois par vidéo présente (via load_registry) — pas de deuxième validation
    en double.

    Retourne :
      n_videos       — nb total de vidéos du registre
      n_present      — nb de vidéos avec au moins une section FORMAT CARD
                        (dupliquée ou non, valide ou non)
      n_valid        — nb de vidéos avec une card présente, UNIQUE et valide
                        (les 3 champs résolus)
      n_blocked      — nb de vidéos bloquées par un statut source explicite
      blocked        — [{"video_id":.., "status":..}] hors erreurs ordinaires
      errors         — [{"video_id":.., "error":..}] pour absente/dupliquée/invalide
      majority       — {"style":.., "realism":.., "hook_mechanic":..} = valeur la
                        plus fréquente par champ parmi les cards valides (None si
                        aucune card valide)
      majority_share — mêmes clés, fraction des cards valides qui partagent cette
                        valeur majoritaire (seuil 2/3 utilisé par --strict)
    """
    n_videos = len(videos)
    n_present = 0
    n_blocked = 0
    blocked = []
    errors = []
    valid_fields = []
    for v in videos:
        vid = v.get("video_id", v.get("ref", "?"))
        inspected = _inspect_one(v)
        if (
            inspected["n_sections"] == 0
            and inspected.get("format_card_status") == "blocked_source_unavailable"
        ):
            n_blocked += 1
            blocked.append(
                {"video_id": vid, "status": "blocked_source_unavailable"}
            )
            continue
        if inspected["n_sections"] == 0:
            errors.append({"video_id": vid, "error": "missing FORMAT CARD"})
            continue
        n_present += 1
        if inspected["n_sections"] > 1:
            errors.append({"video_id": vid, "error": "duplicate FORMAT CARD sections"})
            continue
        if not inspected["valid"]:
            errors.append({"video_id": vid, "error": "; ".join(inspected["errors"])})
            continue
        valid_fields.append(inspected["card"]["fields"])

    n_valid = len(valid_fields)
    majority, majority_share = {}, {}
    for out_key, fcr_key in (
        ("style", "video_style"),
        ("realism", "realism"),
        ("hook_mechanic", "hook_mechanic"),
    ):
        if not valid_fields:
            majority[out_key], majority_share[out_key] = None, 0.0
            continue
        value, count = Counter(f[fcr_key] for f in valid_fields).most_common(1)[0]
        majority[out_key], majority_share[out_key] = value, count / n_valid

    return {
        "n_videos": n_videos,
        "n_present": n_present,
        "n_valid": n_valid,
        "n_blocked": n_blocked,
        "blocked": blocked,
        "errors": errors,
        "majority": majority,
        "majority_share": majority_share,
    }


def parse_cards(videos, report=None):
    """Taxonomie depuis les FORMAT CARDs archivées (labels fixes, vote majoritaire
    parmi les cards valides). Retourne (style, realism, hook_mechanic) SEULEMENT
    si la niche est complète (chaque vidéo a une card présente/valide/unique) ;
    sinon None — une card partielle n'active plus jamais la voie noble, le
    fallback mots-clés prend le relais dans compile_brief.

    `report` est le rapport produit par inspect_cards(videos), s'il est déjà
    disponible ; son omission conserve l'API parse_cards(videos)."""
    if not videos:
        return None
    if report is None:
        report = inspect_cards(videos)
    if report["n_valid"] != report["n_videos"]:
        return None
    m = report["majority"]
    return m["style"], m["realism"], m["hook_mechanic"]


# ponytail: fallback mots-clés quand aucune card archivée (anciennes niches dont
# seule la synthèse prose existe) — les cards taxonomiques priment via parse_cards.
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
        if re.search(pat, formula_text, re.IGNORECASE):
            style, realism = s, r
            break
    hook_mechanic = "other"
    for pat, h in HOOK_KEYWORDS:
        if re.search(pat, formula_text, re.IGNORECASE):
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
    m = re.search(r"```\n(.*?)```", hook_block, re.DOTALL)
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

    wpm, label = voice_wpm.get_wpm(alias, language=language, postproc="cut")
    profile = voice_wpm.get_profile(alias, language=language) or {}
    voice_id = profile.get("voice_id", f"TODO(profil {alias} sans voice_id)")
    return voice_id, wpm, f"voice_wpm.json '{alias}' lang={language}: {label}"


# --- SOT moteurs --------------------------------------------------------------
def engine_provenance(niche):
    """(default_line, hero_line) lues d'ENGINE-FACTS, ou None si aucun verdict
    par-niche ('défaut <niche>') — on ne devine JAMAIS un moteur non testé :
    le brief sort alors avec des entrées TODO(engine-facts)."""
    text = ENGINE_FACTS.read_text(encoding="utf-8")
    lines = [ln.strip("- ").strip() for ln in text.splitlines()]
    default = next(
        (ln for ln in lines if re.search(rf"défaut {niche}", ln, re.IGNORECASE)), None
    )
    if not default:
        return None
    hero = next(
        (ln for ln in lines if re.search(r"hero shots", ln, re.IGNORECASE)), default
    )
    fmt = lambda ln: f"ENGINE-FACTS (Shared/ENGINE-FACTS.md): {ln[:160]}"
    return fmt(default), fmt(hero)


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
def compile_brief(niche, voice=None, language="fr", strict=False):
    """Compile un brief exécutable ; lève ValueError en --strict (cf. plus bas)."""
    brief, _card_report = _compile_brief_full(niche, voice, language, strict)
    return brief


def _compile_brief_full(niche, voice=None, language="fr", strict=False):
    """Comme compile_brief, mais retourne aussi le card_report déjà calculé en
    interne — évite à main() de relire le registre + rappeler inspect_cards()
    juste pour le rapport de couverture passé à readiness()."""
    target_s, shot_s = sc.load_sot()
    videos = load_registry(niche)
    formula_path, formula_text = find_formula(videos)
    assert formula_text, (
        f"CHANNEL FORMULA introuvable dans {FORMATS} pour la niche {niche}"
    )

    style, realism, hook_mechanic, hook_template, constant, slots = derive_format(
        formula_text
    )
    # les cards taxonomiques archivées priment sur l'inférence mots-clés, mais
    # SEULEMENT quand la couverture est complète (règle du plan) — une card
    # partielle/invalide/dupliquée n'active jamais la voie noble.
    card_report = inspect_cards(videos)
    from_cards = parse_cards(videos, report=card_report)
    if from_cards:
        style, realism, hook_mechanic = from_cards
    else:
        print(
            f"[{niche}] {card_report['n_valid']}/{card_report['n_videos']} "
            "cards — fallback keywords"
        )

    if strict:
        ref_by_id = {v["video_id"]: v["ref"] for v in videos}
        problems = [
            f"{ref_by_id.get(e['video_id'], e['video_id'])}: {e['error']}"
            for e in card_report["errors"]
        ]
        problems.extend(
            f"{ref_by_id.get(entry['video_id'], entry['video_id'])}: {entry['status']}"
            for entry in card_report.get("blocked", [])
        )
        if card_report["n_valid"] > 0:
            low = [
                field
                for field, share in card_report["majority_share"].items()
                if share < 2 / 3
            ]
            if low:
                problems.append(f"majorité < 2/3 pour: {', '.join(low)}")
        if problems:
            raise ValueError(
                f"[{niche}] --strict : couverture/validité/majorité des FORMAT "
                "CARDs insuffisante:\n  " + "\n  ".join(problems)
            )

    frames_dir = FRAMES / niche
    if frames_dir.is_dir():
        constant["frames_ref"] = f"Projects/Sourcing/frames/{niche}/"

    voice_id, wpm, wpm_source = load_voice(niche, voice, language)
    engines = engine_provenance(niche)

    beats = build_beats(target_s, wpm, hook_template, constant)
    shots = build_shots(beats, shot_s)

    camera = constant.get("camera", constant.get("cameras", ""))
    style_line = next(iter(constant.values())) if constant else style
    hero_prompt = f"hero shot (hook 0-3s): {style_line} — {camera or 'plan fixe / drift lent'} — <topic>"
    body_prompt = f"{style_line} — {camera or 'plan fixe / drift lent'} — beat courant du script, <topic>"
    if engines:
        default_prov, hero_prov = engines
        prompt_pack = [
            {
                "id": "p_hero",
                "engine": "seedance",
                "mode": "pro",
                "sound": "off",
                "prompt": hero_prompt,
                "provenance": hero_prov,
            },
            {
                "id": "p_body",
                "engine": "kling3_0",
                "mode": "std",
                "sound": "off",
                "prompt": body_prompt,
                "provenance": default_prov,
            },
        ]
    else:
        todo = (
            f"TODO: aucun fait 'défaut {niche}' dans ENGINE-FACTS — tester les "
            "moteurs (gate pilote) puis consigner le verdict avant production"
        )
        prompt_pack = [
            {
                "id": "p_hero",
                "engine": "TODO(engine-facts)",
                "prompt": hero_prompt,
                "provenance": todo,
            },
            {
                "id": "p_body",
                "engine": "TODO(engine-facts)",
                "prompt": body_prompt,
                "provenance": todo,
            },
        ]
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
        "prompt_pack": prompt_pack,
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
    return brief, card_report


def readiness(brief, format_report=None):
    """Signaux 'niche prête ?' lus du brief seul (+ rapport cards optionnel) —
    les TODO/fallback silencieux qu'on veut voir AVANT de faire confiance à la
    sortie (surtout niche fraîche). Retourne la liste des manques ([] = tout
    couplé). format_report (dict retourné par inspect_cards) est une catégorie
    d'avertissement séparée des avertissements voix/moteur existants — ne les
    fusionne pas. Les blocages source sont signalés explicitement, séparément
    des erreurs ordinaires de couverture."""
    warn = []
    if str(brief["script"]["voice_id"]).startswith("TODO"):
        warn.append(
            "voix NON calibrée (budget mots sur wpm _default) -> calibrate-voice"
        )
    if any(str(p["engine"]).startswith("TODO") for p in brief["prompt_pack"]):
        warn.append("aucun verdict moteur dans ENGINE-FACTS -> gate pilote avant prod")
    if brief["format"]["style"] == "other":
        warn.append("style='other' : pas de FORMAT CARD exploitable -> extract-format")
    if brief["format"]["hook_mechanic"] == "other":
        warn.append("hook_mechanic='other' : mécanique de hook non résolue")
    if format_report:
        if format_report.get("n_blocked", 0):
            statuses = sorted(
                {entry["status"] for entry in format_report.get("blocked", [])}
            )
            warn.append("couverture FORMAT CARD bloquée: " + ", ".join(statuses))
        if format_report["n_valid"] != format_report["n_videos"]:
            warn.append(
                f"couverture FORMAT CARD incomplète: {format_report['n_valid']}/"
                f"{format_report['n_videos']} cards valides -> extract-format sur "
                "les vidéos manquantes/invalides"
            )
        elif format_report["n_valid"] > 0:
            low = [
                field
                for field, share in format_report["majority_share"].items()
                if share < 2 / 3
            ]
            if low:
                warn.append(
                    "majorité FORMAT CARD sous le seuil 2/3 pour: "
                    f"{', '.join(low)} -> format hétérogène, envisager un "
                    "cluster/formula séparé"
                )
    return warn


def main():
    ap = argparse.ArgumentParser(description="Compile format_card -> brief.json")
    ap.add_argument("niche")
    ap.add_argument("--voice", help="alias voice_wpm.json (défaut: auto par niche)")
    ap.add_argument("--language", default="fr")
    ap.add_argument("--out")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="lève si couverture/validité/majorité des FORMAT CARDs insuffisante",
    )
    args = ap.parse_args()

    try:
        brief, card_report = _compile_brief_full(
            args.niche, voice=args.voice, language=args.language, strict=args.strict
        )
    except ValueError as e:
        print(f"ERREUR: {e}")
        sys.exit(1)

    out = Path(args.out) if args.out else HERE / f"brief_{args.niche}.json"
    out.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK — brief valide ecrit: {out}")
    print(
        f"  beats: {len(brief['script']['beats'])}  shots: {len(brief['shots'])}  "
        f"wpm: {brief['script']['target_wpm']}  voice: {brief['script']['voice_id']}"
    )
    warn = readiness(brief, card_report)
    if warn:
        print("  ⚠ niche pas encore prête:")
        for w in warn:
            print(f"    - {w}")
    else:
        print("  ✓ couplages résolus : voix + moteur + taxonomie")


if __name__ == "__main__":
    main()
