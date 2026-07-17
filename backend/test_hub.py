"""Tests du scan Niche Hub. hub.py est autonome (pas d'import de main),
donc pas de stubs R2. Le test d'intégration se skippe si le vault n'est
pas accessible (run hors conteneur sans vault local)."""

import os
from pathlib import Path

import hub
import pytest
from fastapi import HTTPException

VAULT = Path(os.environ.get("VAULT_DIR", "/vault"))
if not VAULT.is_dir():
    # Run pytest sur l'hôte Windows : le vault est à cet emplacement fixe.
    VAULT = Path(r"C:\Users\dbele\Documents\ObsidianVault\Wiki_Claude")

needs_vault = pytest.mark.skipif(not VAULT.is_dir(), reason="vault non accessible")


@needs_vault
def test_build_hub_trois_niches_et_champs():
    data = hub.build_hub(VAULT)
    by_key = {n["key"]: n for n in data["niches"]}
    assert {"neon_psycho", "pc-repair", "stickman"} <= set(by_key)

    # neon_psycho : transcripts avec vues + au moins une vignette
    neon = by_key["neon_psycho"]["sourcing"]["videos"]
    t = [v for v in neon if v["source"] == "transcript"]
    assert t and any(v["vues"] for v in t)
    assert any(v["thumb"] for v in t)
    assert any(v["card_ref"] for v in t)

    # pc-repair : chaînes + entrées library (vues null par construction)
    pc = by_key["pc-repair"]
    assert pc["sourcing"]["chaines"]
    lib = [v for v in pc["sourcing"]["videos"] if v["source"] == "library"]
    assert lib and all(v["vues"] is None for v in lib)

    # stickman : aucun sourcing, production datée via published.json
    stick = by_key["stickman"]
    assert stick["sourcing"]["videos"] == []
    prod = stick["production"]["videos"]
    assert prod and any(v["date"] for v in prod)
    # les drafts _ sont exclus partout
    for n in data["niches"]:
        assert all(not v["slug"].startswith("_") for v in n["production"]["videos"])


def test_resolve_frame_traversal():
    with pytest.raises(HTTPException) as e:
        hub.resolve_frame(Path("/nonexistent/frames"), "../../etc/passwd")
    assert e.value.status_code == 404


def test_resolve_frame_extension_non_image(tmp_path):
    (tmp_path / "AGENTS.md").write_text("x")
    with pytest.raises(HTTPException) as e:
        hub.resolve_frame(tmp_path, "AGENTS.md")
    assert e.value.status_code == 404
