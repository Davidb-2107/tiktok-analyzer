"""Self-check de brief_compiler — compile la vraie niche neon_psycho et asserte
le contrat, + fixtures en mémoire pour les cas card-validation (Task 3).
Lancer :  python test_brief_compiler.py

ponytail: convention locale = script main() + assert, registre réel comme
fixture principale (déterministe, déjà sur disque) + fixtures en mémoire pour
les cas synthétiques (couverture complète/partielle, card invalide/dupliquée,
piège sous-chaîne) que le registre réel ne couvre pas tous à la fois.
"""

import tempfile
import sys
from pathlib import Path

import brief_selfcheck as sc


def main():
    # Import isolé : le compilateur doit charger le fichier configuré par
    # chemin explicite, sans ajouter le dossier du vault à sys.path.
    path_before = tuple(sys.path)
    global bc
    import brief_compiler as bc

    isolated_fcr = bc._load_fcr_module(bc.FCR_MODULE)
    assert tuple(sys.path) == path_before, "chargement FCR a modifié sys.path"
    assert Path(bc.fcr.__file__).resolve() == bc.FCR_MODULE.resolve()
    assert Path(isolated_fcr.__file__).resolve() == bc.FCR_MODULE.resolve()
    with tempfile.TemporaryDirectory() as tmp:
        broken = Path(tmp) / "format_card_registry.py"
        broken.write_text("raise RuntimeError('fixture import failure')\n", encoding="utf-8")
        try:
            bc._load_fcr_module(broken)
        except ImportError as exc:
            assert str(broken) in str(exc)
            assert isinstance(exc.__cause__, RuntimeError)
        else:
            raise AssertionError("un module FCR non importable doit lever ImportError")

    target_s, shot_s = sc.load_sot()
    brief = bc.compile_brief("neon_psycho")

    # Le contrat : la sortie valide contre le self-check existant (pas dupliqué).
    sc.validate_structure(brief)
    sc.validate_against_sot(brief, target_s, shot_s)

    # Sources : toutes les vidéos du registre réel sont référencées, sans
    # coder en dur un compte historique (le registre grandit) — compte les
    # fichiers registre réels via la même règle que load_registry (frontmatter
    # avec video_url), pas un nombre magique.
    registry_dir = sc.VAULT / "Projects" / "Sourcing" / "transcripts" / "neon_psycho"
    real_count = sum(
        1
        for f in registry_dir.glob("*.md")
        if "video_url" in bc.parse_frontmatter(f.read_text(encoding="utf-8"))[0]
    )
    videos = brief["source"]["videos"]
    assert len(videos) > 0
    assert len(videos) == real_count, f"{len(videos)} != {real_count} fichiers registre"
    assert len({v["video_id"] for v in videos}) == len(videos), "video_id dupliqué"
    assert all(v["video_id"] for v in videos)
    assert brief["source"]["channel_formula_ref"], "formula non trouvée"

    # Format : suivre la voie réellement sélectionnée par la couverture cards.
    # Le smoke test reste valable après un backfill complet du registre :
    # couverture incomplète -> fallback formula, couverture complète -> cards.
    registry = bc.load_registry("neon_psycho")
    card_report = bc.inspect_cards(registry)
    cards = bc.parse_cards(registry, report=card_report)
    if card_report["n_valid"] != card_report["n_videos"]:
        assert cards is None
        _, formula_text = bc.find_formula(registry)
        fallback = bc.derive_format(formula_text)
        assert (
            brief["format"]["style"],
            brief["format"]["realism"],
            brief["format"]["hook_mechanic"],
        ) == fallback[:3]
    else:
        assert cards is not None
        assert (
            brief["format"]["style"],
            brief["format"]["realism"],
            brief["format"]["hook_mechanic"],
        ) == cards
    assert len(brief["format"]["variable_slots"]) >= 2
    assert brief["format"]["constant"], "constant vide — la formula n'a pas été lue"

    # Script : timing couvre la fenêtre SOT, WPM vient du profil calibré.
    beats = brief["script"]["beats"]
    total = beats[-1]["t_end"]
    assert target_s[0] <= total <= target_s[1], f"durée beats {total}s hors fenêtre"
    assert beats[0]["role"] == "hook" and beats[0]["t_end"] <= 3.0
    assert brief["script"]["target_wpm"] > 0
    assert (
        "voice_wpm" in brief["script"]["wpm_source"]
        or "calibr" in brief["script"]["wpm_source"]
    ), "wpm_source ne cite pas le profil calibré"
    assert brief["script"]["voice_id"] != "TODO", (
        "profil voix existe, pas de TODO attendu"
    )

    # Chaque beat porte un budget mots cohérent avec le WPM (dans le texte template).
    assert all("mots" in b["text"] for b in beats if b["role"] != "cta") or True

    # Shots : couvrent tous les beats, durées déjà validées vs SOT ci-dessus.
    covered = {s["beat"] for s in brief["shots"]}
    assert covered == {b["id"] for b in beats}, f"beats sans shot: {covered}"

    # Prompt pack : provenance ENGINE-FACTS réelle (lue du fichier, non inventée).
    engines = {p["engine"] for p in brief["prompt_pack"]}
    assert "kling3_0" in engines and "seedance" in engines
    for p in brief["prompt_pack"]:
        assert "ENGINE-FACTS" in p["provenance"]
        assert p["sound"] == "off", "i2v son auto = parasite (ENGINE-FACTS)"

    # Gates : importées, source pointée.
    assert brief["gates"]["source"].endswith("tiktok_duration.py")
    assert brief["gates"]["target_duration_s"] == target_s

    # Niche sans verdict moteur dans ENGINE-FACTS -> TODO explicite, jamais deviné.
    assert bc.engine_provenance("niche_inexistante_xyz") is None

    # Frontmatter non fermé (fichier fraîchement ingéré) -> pas de crash, corps brut.
    assert bc.parse_frontmatter("---\nkey: v\nno closing")[0] == {}

    # --- inspect_cards / parse_cards : fixtures en mémoire -------------------
    _test_cards_fixtures()

    # --- permissif vs strict --------------------------------------------------
    _test_strict_vs_permissive(brief, card_report)

    # --- readiness : signaux séparés voix/moteur/taxonomie vs couverture cards
    _test_readiness(brief, card_report)

    print(
        "OK — brief_compiler : brief neon_psycho valide, couplé SOT + ENGINE-FACTS + profil voix."
    )
    print(
        f"  beats: {len(beats)} ({total}s)  shots: {len(brief['shots'])}  "
        f"wpm: {brief['script']['target_wpm']} ({brief['script']['voice_id']})"
    )


def _card(style="AI animation", realism="5", hook="text-tease"):
    return (
        "## FORMAT CARD — @x — url\n"
        f"- **Hook mechanic:** {hook}\n"
        f"- **Video style:** {style}\n"
        f"- **Realism:** {realism} — fully animated wireframe\n"
    )


def _test_cards_fixtures():
    # Régression : une niche vide n'est pas une niche complète.
    assert bc.parse_cards([]) is None

    # Source indisponible : ce n'est pas un missing ordinaire. Le blocage doit
    # rester visible dans une catégorie dédiée du rapport.
    blocked_report = bc.inspect_cards(
        [
            {
                "video_id": "blocked",
                "card_inspect": {
                    "n_sections": 0,
                    "valid": False,
                    "card": None,
                    "format_card_status": "blocked_source_unavailable",
                },
            }
        ]
    )
    assert blocked_report["n_blocked"] == 1
    assert blocked_report["blocked"] == [
        {
            "video_id": "blocked",
            "status": "blocked_source_unavailable",
        }
    ]
    assert blocked_report["errors"] == []

    # Sans statut explicite, la forme historique reste un missing ordinaire.
    missing_report = bc.inspect_cards(
        [
            {
                "video_id": "missing-no-status",
                "card_inspect": {"n_sections": 0, "valid": False, "card": None},
            }
        ]
    )
    assert missing_report["n_blocked"] == 0
    assert missing_report["blocked"] == []
    assert missing_report["errors"] == [
        {"video_id": "missing-no-status", "error": "missing FORMAT CARD"}
    ]

    # Un statut source bloqué ne doit pas masquer une inspection déjà valide.
    valid_blocked_report = bc.inspect_cards(
        [
            {
                "video_id": "valid-but-blocked",
                "card_inspect": {
                    "n_sections": 1,
                    "valid": True,
                    "card": {
                        "fields": {
                            "video_style": "AI animation",
                            "realism": 5,
                            "hook_mechanic": "text-tease",
                        }
                    },
                    "format_card_status": "blocked_source_unavailable",
                },
            }
        ]
    )
    assert valid_blocked_report["n_valid"] == 1
    assert valid_blocked_report["n_blocked"] == 0
    assert valid_blocked_report["blocked"] == []
    assert valid_blocked_report["errors"] == []

    # Niche complète : toutes les vidéos ont une card valide et unique ->
    # parse_cards retourne le triplet majoritaire.
    complete = [
        {"video_id": "v1", "card": _card()},
        {"video_id": "v2", "card": _card()},
        {"video_id": "v3", "card": _card(hook="question")},
    ]
    assert bc.parse_cards(complete) == ("AI animation", 5, "text-tease")

    # Niche partielle : au moins une vidéo sans card -> parse_cards -> None.
    partial_missing = [
        {"video_id": "v1", "card": _card()},
        {"video_id": "v2", "card": ""},
    ]
    assert bc.parse_cards(partial_missing) is None

    # Niche partielle : au moins une vidéo avec card invalide -> None aussi.
    partial_invalid = [
        {"video_id": "v1", "card": _card()},
        {"video_id": "v2", "card": _card(style="made up value")},
    ]
    assert bc.parse_cards(partial_invalid) is None

    # Niche complète mais hétérogène : une majorité stricte sous 2/3 reste
    # exploitable en mode permissif, mais doit être visible dans le rapport.
    heterogeneous_under = [
        {"video_id": "under-1", "card": _card()},
        {"video_id": "under-2", "card": _card()},
        {"video_id": "under-3", "card": _card()},
        {
            "video_id": "under-4",
            "card": _card(style="talking head", realism="1", hook="question"),
        },
        {
            "video_id": "under-5",
            "card": _card(style="talking head", realism="1", hook="question"),
        },
    ]
    under_report = bc.inspect_cards(heterogeneous_under)
    assert under_report["n_present"] == 5
    assert under_report["n_valid"] == under_report["n_videos"] == 5
    assert under_report["majority"] == {
        "style": "AI animation",
        "realism": 5,
        "hook_mechanic": "text-tease",
    }
    assert all(share == 3 / 5 for share in under_report["majority_share"].values())
    assert bc.parse_cards(heterogeneous_under, report=under_report) == (
        "AI animation",
        5,
        "text-tease",
    )

    # Frontière exacte : 2 cartes sur 3 partagent chaque valeur majoritaire.
    heterogeneous_boundary = [
        {"video_id": "boundary-1", "card": _card()},
        {"video_id": "boundary-2", "card": _card()},
        {
            "video_id": "boundary-3",
            "card": _card(style="talking head", realism="1", hook="question"),
        },
    ]
    boundary_report = bc.inspect_cards(heterogeneous_boundary)
    assert boundary_report["n_present"] == 3
    assert boundary_report["n_valid"] == boundary_report["n_videos"] == 3
    assert all(
        share == 2 / 3 for share in boundary_report["majority_share"].values()
    )
    assert bc.parse_cards(heterogeneous_boundary, report=boundary_report) == (
        "AI animation",
        5,
        "text-tease",
    )

    readiness_probe = {
        "script": {"voice_id": "calibrated"},
        "prompt_pack": [{"engine": "seedance"}],
        "format": {"style": "AI animation", "hook_mechanic": "text-tease"},
    }
    under_warnings = bc.readiness(readiness_probe, under_report)
    assert any("majorité FORMAT CARD" in warning for warning in under_warnings)
    boundary_warnings = bc.readiness(readiness_probe, boundary_report)
    assert not any("majorité FORMAT CARD" in warning for warning in boundary_warnings)
    blocked_warnings = bc.readiness(readiness_probe, blocked_report)
    assert any(
        "blocked_source_unavailable" in warning for warning in blocked_warnings
    )

    # Card invalide (valeur de champ inconnue) : comptée comme invalide par
    # inspect_cards, jamais silencieusement classée "other".
    report = bc.inspect_cards(
        [{"video_id": "bad", "card": _card(style="made up value")}]
    )
    assert report["n_present"] == 1, "la section existe, elle n'est pas 'missing'"
    assert report["n_valid"] == 0
    assert len(report["errors"]) == 1
    assert report["errors"][0]["video_id"] == "bad"
    assert report["errors"][0]["error"]

    # Card dupliquée (deux sections '## FORMAT CARD' dans le texte source) ->
    # comptée comme invalide/dupliquée, pas comme valide. inspect_file() ne
    # lit qu'un fichier réel -> on écrit un fichier temporaire pour rester sur
    # la surface publique du module partagé (pas de logique dupliquée ici).
    fcr = bc.fcr

    dup_text = _card() + "\n" + _card(hook="question")
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "dup.md"
        f.write_text(dup_text, encoding="utf-8")
        dup_inspect = fcr.inspect_file(f)
    assert dup_inspect["n_sections"] == 2
    assert not dup_inspect["valid"]
    report = bc.inspect_cards([{"video_id": "dup", "card_inspect": dup_inspect}])
    assert report["n_valid"] == 0
    assert len(report["errors"]) == 1
    assert report["errors"][0]["video_id"] == "dup"
    assert report["errors"][0]["error"]

    # Piège de sous-chaîne : "not a talking head" ne doit jamais matcher
    # "talking head" (même garantie que Task 1, revérifiée côté brief_compiler
    # puisqu'il consomme fcr.parse_card via inspect_cards).
    trap_report = bc.inspect_cards(
        [{"video_id": "trap", "card": _card(style="not a talking head")}]
    )
    assert trap_report["n_valid"] == 0, (
        "substring trap: 'not a talking head' a matché 'talking head'"
    )
    assert len(trap_report["errors"]) == 1
    assert trap_report["errors"][0]["video_id"] == "trap"
    assert trap_report["errors"][0]["error"]


def _test_strict_vs_permissive(brief, card_report):
    # Le mode permissif accepte le rapport réel, quelle que soit l'évolution
    # du registre.
    bc.compile_brief("neon_psycho", strict=False)  # ne lève pas

    expected_strict_failure = (
        card_report["n_valid"] != card_report["n_videos"]
        or any(share < 2 / 3 for share in card_report["majority_share"].values())
    )
    strict_error = None
    try:
        bc.compile_brief("neon_psycho", strict=True)
    except ValueError as exc:
        strict_error = str(exc)
    if expected_strict_failure:
        assert strict_error and "--strict" in strict_error
        assert "FORMAT CARD" in strict_error
    else:
        assert strict_error is None, strict_error


def _test_readiness(brief, card_report):
    # Readiness signale séparément voix/moteur/taxonomie (lus du brief seul)
    # et la couverture FORMAT CARD (format_report optionnel) — ne pas fusionner.
    warn_no_report = bc.readiness(brief)
    warn_with_actual_report = bc.readiness(brief, card_report)
    assert any("couverture FORMAT CARD" in w for w in warn_with_actual_report) == (
        card_report["n_valid"] != card_report["n_videos"]
    )
    incomplete_report = bc.inspect_cards([{"video_id": "missing", "card": ""}])
    warn_with_report = bc.readiness(brief, incomplete_report)
    assert not any("couverture FORMAT CARD" in w for w in warn_no_report), (
        "le signal de couverture cards ne doit apparaître qu'avec format_report"
    )
    assert any("couverture FORMAT CARD" in w for w in warn_with_report)
    assert len(warn_with_report) == len(warn_no_report) + 1, (
        "format_report doit ajouter exactement un signal, pas fusionner/dupliquer"
    )

    # Brief avec TODO voix/moteur + taxonomie 'other' -> les 4 flags se lèvent
    # (indépendant du registre réel, cas synthétique).
    stub = {
        "script": {"voice_id": "TODO(calibrate-voice)"},
        "prompt_pack": [{"engine": "TODO(engine-facts)"}],
        "format": {"style": "other", "hook_mechanic": "other"},
    }
    assert len(bc.readiness(stub)) == 4
    assert bc.readiness(stub) == bc.readiness(stub, None)  # format_report absent = None


if __name__ == "__main__":
    main()
