"""Minimal public surface used by brief_compiler in CI."""

import json
from pathlib import Path


_DATA = json.loads((Path(__file__).parent / "voice_wpm.json").read_text(encoding="utf-8"))


def get_profile(alias, language="fr"):
    profile = _DATA.get(alias)
    if not profile:
        return None
    return {"voice_id": profile["voice_id"], **profile.get(language, {})}


def get_wpm(alias, language="fr", postproc="cut"):
    profile = _DATA[alias]
    lang = profile.get(language, {})
    return float(lang.get("wpm", _DATA.get("_default", 180.0))), lang.get(
        "label", "synthetic CI calibration"
    )
