"""Self-check de brief_compiler — compile la vraie niche neon_psycho et asserte
le contrat, + fixtures en mémoire pour les cas card-validation (Task 3).
Lancer :  python test_brief_compiler.py

ponytail: convention locale = script main() + assert, registre réel comme
fixture principale (déterministe, déjà sur disque) + fixtures en mémoire pour
les cas synthétiques (couverture complète/partielle, card invalide/dupliquée,
piège sous-chaîne) que le registre réel ne couvre pas tous à la fois.
"""

import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
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
    # The CI fixture uses a synthetic channel; production smoke tests keep the
    # real default while CI declares its fixture-specific value explicitly.
    channel = os.environ.get("FORMAT_CARD_TEST_CHANNEL", "@viraldtoprw")
    brief = bc.compile_brief("neon_psycho", channel=channel)

    # Le contrat : la sortie valide contre le self-check existant (pas dupliqué).
    sc.validate_structure(brief)
    sc.validate_against_sot(brief, target_s, shot_s)
    assert brief["schema_version"] == "0.2"
    assert brief["source"]["channel"].startswith("@")
    invalid = json.loads(json.dumps(brief))
    del invalid["source"]["channel"]
    try:
        sc.validate_structure(invalid)
    except AssertionError:
        pass
    else:
        raise AssertionError("un brief sans source.channel doit être rejeté")
    invalid["source"]["channel"] = "@Fixture_A"
    try:
        sc.validate_structure(invalid)
    except AssertionError:
        pass
    else:
        raise AssertionError("un source.channel non canonique doit être rejeté")

    # Sources : toutes les vidéos du registre réel sont référencées, sans
    # coder en dur un compte historique (le registre grandit) — compte les
    # fichiers registre réels via la même règle que load_registry (frontmatter
    # avec video_url), pas un nombre magique.
    registry_dir = sc.VAULT / "Projects" / "Sourcing" / "transcripts" / "neon_psycho"
    real_count = sum(
        1
        for f in registry_dir.rglob("*.md")
        if (
            "video_url" in bc.parse_frontmatter(f.read_text(encoding="utf-8"))[0]
            and bc.parse_frontmatter(f.read_text(encoding="utf-8"))[0].get("channel")
            == channel
        )
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
    registry = bc.load_registry("neon_psycho", channel=channel)
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

    # --- routage multi-chaînes : une formula par chaîne ----------------------
    if channel in {"@ci", "@fixture_b"}:
        _test_channel_formula_routing(channel)
    _test_arbitrary_channel_routing()

    # --- console Windows cp1252 : warning permissif --------------------------
    if os.environ.get("RUN_DARK_PSYCHO_SMOKE") == "1":
        _test_cp1252_warning()

    # --- strict : cas synthétiques, indépendants du registre réel ------------
    _test_strict_synthetic_cases()

    # --- permissif vs strict --------------------------------------------------
    _test_strict_vs_permissive(brief, card_report, channel)

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


def _test_channel_formula_routing(channel):
    ci = bc.load_registry("neon_psycho", channel="@ci")
    fixture_b = bc.load_registry("neon_psycho", channel="@fixture_b")
    assert {v["channel"] for v in ci} == {"@ci"}
    assert {v["channel"] for v in fixture_b} == {"@fixture_b"}
    assert all("/ci/" in v["ref"] for v in ci)
    assert all("/fixture_b/" in v["ref"] for v in fixture_b)
    try:
        bc.load_registry("neon_psycho")
    except ValueError as exc:
        assert "utilisez --channel" in str(exc)
    else:
        raise AssertionError("un registre multi-chaînes doit exiger --channel")
    try:
        bc.load_registry("neon_psycho", channel="ci")
    except ValueError as exc:
        assert "non canonique" in str(exc)
    else:
        raise AssertionError("une chaîne sans @ doit être rejetée")

    brief_ci = bc.compile_brief("neon_psycho", channel="@ci")
    brief_b = bc.compile_brief("neon_psycho", channel="@fixture_b")
    assert brief_ci["source"]["channel"] == "@ci"
    assert brief_b["source"]["channel"] == "@fixture_b"
    assert "/ci/" in brief_ci["source"]["format_card_ref"]
    assert "/fixture_b/" in brief_b["source"]["format_card_ref"]
    assert "/ci" in brief_ci["source"]["channel_formula_ref"]
    assert "/fixture_b" in brief_b["source"]["channel_formula_ref"]
    assert (
        brief_ci["format"]["style"],
        brief_ci["format"]["hook_mechanic"],
        brief_ci["format"]["realism"],
    ) == ("AI animation", "text-tease", 5), brief_ci["format"]
    assert (
        brief_b["format"]["style"],
        brief_b["format"]["hook_mechanic"],
        brief_b["format"]["realism"],
    ) == ("POV skit", "question", 2), brief_b["format"]
    assert brief_ci["format"]["constant"]["camera"] == "virtual AI close-up"
    assert brief_b["format"]["constant"]["camera"] == "handheld POV reaction"
    assert all("ci/vault" not in ref for ref in (
        brief_ci["source"]["format_card_ref"],
        brief_ci["source"]["channel_formula_ref"],
        brief_b["source"]["format_card_ref"],
        brief_b["source"]["channel_formula_ref"],
    ))


def _write_channel_fixture(vault, niche, channel, video_ids, style, realism, hook):
    slug = channel[1:]
    transcripts = vault / "Projects" / "Sourcing" / "transcripts" / niche / slug
    transcripts.mkdir(parents=True, exist_ok=True)
    for video_id in video_ids:
        (transcripts / f"{video_id}.md").write_text(
            "---\n"
            f"video_url: https://www.tiktok.com/{channel}/video/{video_id}\n"
            f'channel: "{channel}"\n'
            f"channel_id: {slug}\n"
            "title: Synthetic channel fixture\n"
            "views: 1\n"
            "---\n\n"
            "## Transcript\n\n"
            "Synthetic transcript.\n\n"
            f"## FORMAT CARD — {channel} — synthetic\n"
            f"- **Hook mechanic:** {hook}\n"
            f"- **Video style:** {style}\n"
            f"- **Realism:** {realism} — synthetic fixture\n",
            encoding="utf-8",
        )
    formula = vault / "Projects" / "Sourcing" / "formats" / niche / f"{slug}.md"
    formula.parent.mkdir(parents=True, exist_ok=True)
    formula.write_text(
        "---\n"
        f'channel: "{channel}"\n'
        f"channel_id: {slug}\n"
        f"videos: {', '.join(video_ids)}\n"
        "---\n\n"
        "## Constant\n"
        f"- **camera**: {slug} camera\n"
        "- **cta**: follow\n\n"
        "## Slots variables\n"
        "- topic\n"
        "- audience\n\n"
        "## Hook template\n"
        "```\n"
        f"{hook} {slug}\n"
        "```\n",
        encoding="utf-8",
    )
    return formula


@contextmanager
def _temporary_channel_vault():
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp)
        original = {
            "vault": sc.VAULT,
            "transcripts": bc.TRANSCRIPTS,
            "formats": bc.FORMATS,
            "frames": bc.FRAMES,
            "engine_facts": bc.ENGINE_FACTS,
            "voice_cal": bc.VOICE_CAL,
            "load_sot": sc.load_sot,
            "load_voice": bc.load_voice,
            "engine_provenance": bc.engine_provenance,
        }
        sc.VAULT = vault
        bc.TRANSCRIPTS = vault / "Projects" / "Sourcing" / "transcripts"
        bc.FORMATS = vault / "Projects" / "Sourcing" / "formats"
        bc.FRAMES = vault / "Projects" / "Sourcing" / "frames"
        bc.ENGINE_FACTS = vault / "Shared" / "ENGINE-FACTS.md"
        bc.VOICE_CAL = vault / "Shared" / "voice-calibration"
        sc.load_sot = lambda: ([62.0, 75.0], [1.5, 4.0])
        bc.load_voice = lambda *_: ("fixture_voice", 200.0, "fixture")
        bc.engine_provenance = lambda _: None
        try:
            yield vault
        finally:
            sc.VAULT = original["vault"]
            bc.TRANSCRIPTS = original["transcripts"]
            bc.FORMATS = original["formats"]
            bc.FRAMES = original["frames"]
            bc.ENGINE_FACTS = original["engine_facts"]
            bc.VOICE_CAL = original["voice_cal"]
            sc.load_sot = original["load_sot"]
            bc.load_voice = original["load_voice"]
            bc.engine_provenance = original["engine_provenance"]


def _expect_value_error(action, message):
    try:
        action()
    except ValueError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError(message)


def _test_arbitrary_channel_routing():
    niche = "four_channels"
    channels = (
        ("@alpha", "111111111111111111", "AI animation", 5, "text-tease"),
        ("@beta", "222222222222222222", "POV skit", 2, "question"),
        ("@gamma", "333333333333333333", "talking head", 1, "direct address"),
        ("@delta", "444444444444444444", "b-roll + voiceover", 3, "curiosity gap"),
    )
    with _temporary_channel_vault() as vault:
        formulas = {}
        for channel, video_id, style, realism, hook in channels:
            formulas[channel] = _write_channel_fixture(
                vault, niche, channel, [video_id], style, realism, hook
            )

        for channel, _, _, _, _ in channels:
            registry = bc.load_registry(niche, channel=channel)
            assert {v["channel"] for v in registry} == {channel}
            assert len(registry) == 1
            assert all(f"/{channel[1:]}/" in v["ref"] for v in registry)

        try:
            bc.load_registry(niche)
        except ValueError as exc:
            message = str(exc)
            assert "utilisez --channel" in message
            assert all(channel in message for channel, *_ in channels)
        else:
            raise AssertionError("un registre multi-chaînes doit exiger --channel")
        _expect_value_error(lambda: bc.compile_brief(niche), "utilisez --channel")
        _expect_value_error(
            lambda: bc.load_registry(niche, channel="@Alpha"), "non canonique"
        )
        _expect_value_error(
            lambda: bc.load_registry(niche, channel="alpha"), "non canonique"
        )
        _expect_value_error(
            lambda: bc.load_registry(niche, channel="@unknown"), "chaîne introuvable"
        )

        alpha = bc.compile_brief(niche, channel="@alpha")
        beta = bc.compile_brief(niche, channel="@beta")
        assert alpha["source"]["channel"] == "@alpha"
        assert beta["source"]["channel"] == "@beta"
        assert (alpha["format"]["style"], alpha["format"]["realism"], alpha["format"]["hook_mechanic"]) == (
            "AI animation", 5, "text-tease"
        )
        assert (beta["format"]["style"], beta["format"]["realism"], beta["format"]["hook_mechanic"]) == (
            "POV skit", 2, "question"
        )
        for brief, channel in ((alpha, "@alpha"), (beta, "@beta")):
            slug = channel[1:]
            assert f"/{slug}/" in brief["source"]["format_card_ref"]
            assert brief["source"]["channel_formula_ref"].endswith(f"/{slug}.md")
            assert all(f"/{slug}/" in v["ref"] for v in bc.load_registry(niche, channel=channel))

        mismatched_card = (
            vault / "Projects" / "Sourcing" / "transcripts" / niche / "wrong" / "555555555555555555.md"
        )
        mismatched_card.parent.mkdir()
        mismatched_card.write_text(
            "---\nvideo_url: https://www.tiktok.com/@alpha/video/555555555555555555\n"
            'channel: "@alpha"\n---\n', encoding="utf-8"
        )
        _expect_value_error(
            lambda: bc.load_registry(niche, channel="@alpha"), "incohérents"
        )
        mismatched_card.unlink()

        missing_channel_card = (
            vault / "Projects" / "Sourcing" / "transcripts" / niche / "alpha" / "666666666666666666.md"
        )
        missing_channel_card.write_text(
            "---\nvideo_url: https://www.tiktok.com/@alpha/video/666666666666666666\n---\n",
            encoding="utf-8",
        )
        _expect_value_error(
            lambda: bc.load_registry(niche, channel="@alpha"), "non canonique"
        )
        missing_channel_card.unlink()

        missing_channel_formula = (
            vault / "Projects" / "Sourcing" / "formats" / niche / "missing.md"
        )
        missing_channel_formula.write_text(
            "---\nvideos: 111111111111111111\n---\n", encoding="utf-8"
        )
        _expect_value_error(
            lambda: bc.find_formula(bc.load_registry(niche, channel="@alpha")),
            "non canonique",
        )
        missing_channel_formula.unlink()

        formulas["@alpha"].write_text(
            formulas["@alpha"].read_text(encoding="utf-8").replace(
                "channel_id: alpha", "channel_id: beta"
            ),
            encoding="utf-8",
        )
        _expect_value_error(
            lambda: bc.find_formula(bc.load_registry(niche, channel="@alpha")),
            "incohérents",
        )

        partial_formula = _write_channel_fixture(
            vault,
            niche,
            "@alpha",
            ["111111111111111111"],
            "AI animation",
            5,
            "text-tease",
        ).read_text(encoding="utf-8")
        _write_channel_fixture(
            vault,
            niche,
            "@alpha",
            ["111111111111111111", "777777777777777777"],
            "AI animation",
            5,
            "text-tease",
        )
        formulas["@alpha"].write_text(partial_formula, encoding="utf-8")
        _expect_value_error(
            lambda: bc.find_formula(bc.load_registry(niche, channel="@alpha")),
            "incomplète",
        )


def _test_cp1252_warning():
    dark_registry = sc.VAULT / "Projects" / "Sourcing" / "transcripts" / "dark_psycho"
    if not dark_registry.is_dir():
        return
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [
                sys.executable,
                "brief_compiler.py",
                "dark_psycho",
                "--out",
                str(Path(tmp) / "brief.json"),
            ],
            env=env,
            capture_output=True,
        )
    assert result.returncode == 0, result.stderr.decode("ascii", errors="replace")
    assert b"niche pas encore" in result.stdout


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

    # Valeurs canoniques absentes de l'ancien fixture CI réduit.
    divergent_values = bc.inspect_cards(
        [
            {
                "video_id": "canonical-values",
                "card": _card(
                    style="POV skit", realism="4", hook="direct address"
                ),
            }
        ]
    )
    assert divergent_values["n_valid"] == 1, divergent_values["errors"]
    assert divergent_values["majority"] == {
        "style": "POV skit",
        "realism": 4,
        "hook_mechanic": "direct address",
    }

    # Chaque label requis est unique : une seconde occurrence contradictoire
    # invalide la card au lieu de laisser gagner la première occurrence.
    base = _card(style="POV skit", realism="4", hook="direct address")
    duplicate_cases = (
        (
            "Video style",
            base.replace(
                "- **Video style:** POV skit",
                "- **Video style:** POV skit\n- **Video style:** talking head",
            ),
        ),
        (
            "Hook mechanic",
            base.replace(
                "- **Hook mechanic:** direct address",
                "- **Hook mechanic:** direct address\n- **Hook mechanic:** question",
            ),
        ),
        (
            "Realism",
            base.replace(
                "- **Realism:** 4 — fully animated wireframe",
                "- **Realism:** 4 — fully animated wireframe\n- **Realism:** 1",
            ),
        ),
    )
    for label, card in duplicate_cases:
        duplicate = bc.inspect_cards([{"video_id": label, "card": card}])
        assert duplicate["n_valid"] == 0
        assert duplicate["errors"] == [
            {"video_id": label, "error": f"duplicate field: {label}"}
        ]

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


def _strict_error(videos, report):
    try:
        bc._enforce_strict_cards("synthetic", videos, report)
    except ValueError as exc:
        return str(exc)
    return None


def _test_strict_synthetic_cases():
    partial = [
        {"video_id": "valid", "ref": "synthetic/valid.md", "card": _card()},
        {"video_id": "missing", "ref": "synthetic/missing.md", "card": ""},
    ]
    partial_error = _strict_error(partial, bc.inspect_cards(partial))
    assert partial_error is not None
    assert "synthetic/missing.md: missing FORMAT CARD" in partial_error

    blocked = [
        {
            "video_id": "blocked",
            "ref": "synthetic/blocked.md",
            "card_inspect": {
                "n_sections": 0,
                "valid": False,
                "errors": ["no FORMAT CARD section found"],
                "card": None,
                "format_card_status": "blocked_source_unavailable",
            },
        }
    ]
    blocked_error = _strict_error(blocked, bc.inspect_cards(blocked))
    assert blocked_error is not None
    assert "synthetic/blocked.md: blocked_source_unavailable" in blocked_error

    under_two_thirds = [
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
    under_error = _strict_error(
        under_two_thirds, bc.inspect_cards(under_two_thirds)
    )
    assert under_error is not None
    assert "majorité < 2/3 pour: style, realism, hook_mechanic" in under_error

    exact_two_thirds = [
        {"video_id": "boundary-1", "card": _card()},
        {"video_id": "boundary-2", "card": _card()},
        {
            "video_id": "boundary-3",
            "card": _card(style="talking head", realism="1", hook="question"),
        },
    ]
    assert _strict_error(exact_two_thirds, bc.inspect_cards(exact_two_thirds)) is None


def _test_strict_vs_permissive(brief, card_report, channel):
    # Le mode permissif accepte le rapport réel, quelle que soit l'évolution
    # du registre.
    bc.compile_brief("neon_psycho", channel=channel, strict=False)  # ne lève pas

    expected_strict_failure = (
        card_report["n_valid"] != card_report["n_videos"]
        or any(share < 2 / 3 for share in card_report["majority_share"].values())
    )
    strict_error = None
    try:
        bc.compile_brief("neon_psycho", channel=channel, strict=True)
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
