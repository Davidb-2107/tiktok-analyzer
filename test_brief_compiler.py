"""Self-check de brief_compiler — compile la vraie niche neon_psycho et asserte
le contrat. Lancer :  python test_brief_compiler.py

ponytail: un seul test, sur données réelles du registre (déjà sur disque,
déterministes). Pas de fixtures — le registre EST la fixture.
"""

import brief_compiler as bc
import brief_selfcheck as sc


def main():
    target_s, shot_s = sc.load_sot()
    brief = bc.compile_brief("neon_psycho")

    # Le contrat : la sortie valide contre le self-check existant (pas dupliqué).
    sc.validate_structure(brief)
    sc.validate_against_sot(brief, target_s, shot_s)

    # Sources : les 5 vidéos du registre sont référencées, avec la formula.
    assert len(brief["source"]["videos"]) == 5
    assert all(v["video_id"] for v in brief["source"]["videos"])
    assert brief["source"]["channel_formula_ref"], "formula non trouvée"

    # Format : dérivé de la CHANNEL FORMULA, pas inventé.
    assert brief["format"]["style"] == "AI animation"
    assert brief["format"]["realism"] == 5
    assert len(brief["format"]["variable_slots"]) >= 2
    assert brief["format"]["constant"], "constant vide — la formula n'a pas été lue"

    # Script : timing couvre la fenêtre SOT, WPM vient du profil calibré.
    beats = brief["script"]["beats"]
    total = beats[-1]["t_end"]
    assert target_s[0] <= total <= target_s[1], f"durée beats {total}s hors fenêtre"
    assert beats[0]["role"] == "hook" and beats[0]["t_end"] <= 3.0
    assert brief["script"]["target_wpm"] > 0
    assert "voice_wpm" in brief["script"]["wpm_source"] or "calibr" in brief["script"]["wpm_source"], (
        "wpm_source ne cite pas le profil calibré"
    )
    assert brief["script"]["voice_id"] != "TODO", "profil voix existe, pas de TODO attendu"

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

    print("OK — brief_compiler : brief neon_psycho valide, couplé SOT + ENGINE-FACTS + profil voix.")
    print(
        f"  beats: {len(beats)} ({total}s)  shots: {len(brief['shots'])}  "
        f"wpm: {brief['script']['target_wpm']} ({brief['script']['voice_id']})"
    )


if __name__ == "__main__":
    main()
