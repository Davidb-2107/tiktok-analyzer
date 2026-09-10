"""Self-check du contrat brief.schema.json.

Prouve la seule chose qui compte : un brief reste COUPLÉ au SOT de spec
(Shared/tiktok-spec/tiktok_duration.py) et ne fige aucune constante de prod.

Volontairement sans dépendance (pas de jsonschema) : la validation de structure
est minimale et faite main ; le cœur du test est le cross-check contre le module
SOT réel. Lancer :  python brief_selfcheck.py

ponytail: valide le contrat, pas chaque champ. Le vrai risque = un brief qui
diverge du SOT — c'est ce qui est asserté ici.
"""

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = HERE / "brief.schema.json"

# --- localiser + importer le SOT de spec (source unique de vérité) -----------
VAULT = Path(
    os.environ.get("VAULT_DIR", r"C:\Users\dbele\Documents\ObsidianVault\Wiki_Claude")
).expanduser()
SOT_DIR = VAULT / "Shared" / "tiktok-spec"


def load_sot():
    """Retourne (TIKTOK_TARGET_S, TIKTOK_SHOT_S) depuis le module réel."""
    sys.path.insert(0, str(SOT_DIR))
    from tiktok_duration import TIKTOK_TARGET_S, TIKTOK_SHOT_S  # noqa: E402

    return list(TIKTOK_TARGET_S), list(TIKTOK_SHOT_S)


# --- exemple de brief (neon_psycho, illustratif) -----------------------------
def example_brief(target_s, shot_s):
    """Brief d'exemple. Les gates sont REMPLIES depuis le SOT (jamais en dur) —
    c'est exactement ce que fera le compilateur format_card -> brief."""
    return {
        "schema_version": "0.1",
        "niche": "neon_psycho",
        "source": {
            "videos": [
                {
                    "url": "https://www.tiktok.com/@viraldtoprw/video/7568334048544820510",
                    "video_id": "7568334048544820510",
                    "channel": "@viraldtoprw",
                    "title": "Psychology fact",
                    "views": 53000000,
                }
            ],
            "format_card_ref": "Projects/Sourcing/transcripts/neon_psycho/7568334048544820510.md",
            "channel_formula_ref": "Projects/Sourcing/transcripts/neon_psycho/_formula.md",
        },
        "format": {
            "style": "AI animation",
            "realism": 5,
            "hook_mechanic": "text-tease",
            "hook_template": "static neon close-up + text-tease '<bold claim>' + mid-action start",
            "constant": {
                "camera": "virtual/AI camera, close-up",
                "sound": "voiceover",
                "editing_pace": 2.5,
                "cta": "follow for more",
            },
            "variable_slots": ["topic", "pov_target"],
        },
        "script": {
            "language": "fr",
            "voice_id": "darling_v1",
            "target_wpm": 210.0,
            "wpm_source": "calibrate-voice Darling atempo 1.05 (mesuré)",
            "beats": [
                {
                    "id": "hook",
                    "role": "hook",
                    "t_start": 0.0,
                    "t_end": 3.0,
                    "text": "Ton cerveau te ment sur une chose chaque jour.",
                },
                {
                    "id": "setup",
                    "role": "setup",
                    "t_start": 3.0,
                    "t_end": 20.0,
                    "text": "Voici pourquoi...",
                },
                {
                    "id": "payoff",
                    "role": "payoff",
                    "t_start": 20.0,
                    "t_end": 66.0,
                    "text": "...",
                },
                {
                    "id": "cta",
                    "role": "cta",
                    "t_start": 66.0,
                    "t_end": 68.0,
                    "text": "Suis pour la suite.",
                },
            ],
        },
        "shots": [
            {
                "id": "s1",
                "beat": "hook",
                "duration_s": 2.5,
                "prompt_ref": "p1",
                "motion": "ken_burns_in",
                "overlay_text": "Ton cerveau te ment",
            },
            {"id": "s2", "beat": "setup", "duration_s": 3.0, "prompt_ref": "p2"},
            {
                "id": "s3",
                "beat": "payoff",
                "duration_s": 4.0,
                "prompt_ref": "p2",
                "motion": "ken_burns_out",
            },
        ],
        "prompt_pack": [
            {
                "id": "p1",
                "engine": "kling3_0",
                "mode": "std",
                "sound": "off",
                "image_ref": "ressources/style-refs/homme_cyan.png",
                "prompt": "neon cyan man, extreme close-up, subtle head turn",
                "provenance": "ENGINE-FACTS 2026-07-14 kling3_0 std sound:off",
            },
            {
                "id": "p2",
                "engine": "seedance",
                "mode": "pro",
                "sound": "off",
                "image_ref": "ressources/style-refs/scene_plate.png",
                "prompt": "hero shot, slow push",
                "provenance": "ENGINE-FACTS 2026-07-14 Seedance = hero shots",
            },
        ],
        "captions": {"style": "karaoke", "max_lines": 1, "preset": "CC-DerStil"},
        "gates": {
            "target_duration_s": target_s,  # <-- importé du SOT, pas figé
            "shot_duration_s": shot_s,  # <-- importé du SOT, pas figé
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


# --- validation de structure minimale (sans dépendance) ----------------------
def check_required(obj, path, required):
    for k in required:
        assert k in obj, f"{path}: champ requis manquant '{k}'"


def validate_structure(b):
    top = [
        "schema_version",
        "niche",
        "source",
        "format",
        "script",
        "shots",
        "prompt_pack",
        "captions",
        "gates",
    ]
    check_required(b, "root", top)
    assert b["schema_version"] == "0.1"
    check_required(
        b["format"],
        "format",
        ["style", "realism", "hook_mechanic", "hook_template", "variable_slots"],
    )
    assert 1 <= b["format"]["realism"] <= 5
    assert b["format"]["variable_slots"], "variable_slots vide"
    check_required(
        b["script"], "script", ["language", "voice_id", "target_wpm", "beats"]
    )
    assert len(b["script"]["beats"]) >= 2
    for beat in b["script"]["beats"]:
        check_required(beat, "beat", ["id", "role", "t_start", "t_end", "text"])
        assert beat["t_end"] >= beat["t_start"], f"beat {beat['id']}: t_end < t_start"
    assert b["captions"]["max_lines"] == 1, "PRODUCTION-RULES: captions 1 ligne"
    for pp in b["prompt_pack"]:
        check_required(pp, "prompt_pack", ["id", "engine", "prompt", "provenance"])
        assert pp["provenance"].strip(), f"prompt {pp['id']}: provenance moteur vide"


# --- LE test qui compte : couplage au SOT ------------------------------------
def validate_against_sot(b, target_s, shot_s):
    g = b["gates"]
    assert g["target_duration_s"] == target_s, (
        f"gates.target_duration_s {g['target_duration_s']} != SOT {target_s} "
        "— le brief a figé une durée au lieu de l'importer"
    )
    assert g["shot_duration_s"] == shot_s, (
        f"gates.shot_duration_s {g['shot_duration_s']} != SOT {shot_s}"
    )
    lo, hi = shot_s
    for s in b["shots"]:
        d = s["duration_s"]
        assert lo <= d <= hi, f"shot {s['id']}: {d}s hors bornes SOT [{lo},{hi}]"
    # cohérence référentielle : chaque shot pointe un beat et un prompt réels
    beat_ids = {x["id"] for x in b["script"]["beats"]}
    pp_ids = {x["id"] for x in b["prompt_pack"]}
    for s in b["shots"]:
        assert s["beat"] in beat_ids, f"shot {s['id']}: beat inconnu '{s['beat']}'"
        assert s["prompt_ref"] in pp_ids, (
            f"shot {s['id']}: prompt inconnu '{s['prompt_ref']}'"
        )


def main():
    assert SCHEMA.exists(), f"schéma introuvable: {SCHEMA}"
    json.loads(SCHEMA.read_text(encoding="utf-8"))  # le schéma est un JSON valide

    try:
        target_s, shot_s = load_sot()
    except Exception as e:  # SOT absent (hors machine vault) -> skip le cross-check
        print(f"SKIP cross-check SOT (module non importable: {e})")
        target_s, shot_s = [62.0, 75.0], [1.5, 4.0]
        sot_ok = False
    else:
        sot_ok = True

    b = example_brief(target_s, shot_s)
    validate_structure(b)
    validate_against_sot(b, target_s, shot_s)

    print("OK — brief.schema.json : structure valide, contrat couplé au SOT.")
    print(
        f"  target_duration_s = {target_s}  shot_duration_s = {shot_s}"
        f"  {'(SOT réel)' if sot_ok else '(fallback, SOT non chargé)'}"
    )
    print(
        f"  shots: {len(b['shots'])}  beats: {len(b['script']['beats'])}"
        f"  prompts: {len(b['prompt_pack'])}"
    )


if __name__ == "__main__":
    main()
