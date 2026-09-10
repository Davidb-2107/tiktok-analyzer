"""Small synthetic FORMAT CARD registry used by CI only.

It intentionally exposes the same public parsing/inspection contract as the
real vault module, without copying any real vault data or implementation.
"""

import re
from pathlib import Path


_STYLES = {"AI animation", "talking head", "b-roll + voiceover"}
_HOOKS = {"text-tease", "question", "bold claim", "mid-action start", "curiosity gap"}


def _sections(text):
    return re.findall(
        r"^## FORMAT CARD\b.*?(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL
    )


def _without_explanation(value):
    """Keep the canonical label before a real-card em-dash explanation."""
    return value.split("—", 1)[0].strip()


def parse_card(text):
    sections = _sections(text)
    if len(sections) != 1:
        return {"valid": False, "errors": ["expected exactly one FORMAT CARD section"], "fields": {}}
    section = sections[0]
    values = {}
    patterns = {
        "hook_mechanic": r"^[-*]\s*\*\*Hook mechanic:\*\*\s*(.+?)\s*$",
        "video_style": r"^[-*]\s*\*\*Video style:\*\*\s*(.+?)\s*$",
        "realism": r"^[-*]\s*\*\*Realism:\*\*\s*(\d+)\b",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, section, flags=re.MULTILINE | re.IGNORECASE)
        if match:
            values[key] = _without_explanation(match.group(1))
    errors = []
    if values.get("video_style") not in _STYLES:
        errors.append("unknown video_style")
    if values.get("hook_mechanic") not in _HOOKS:
        errors.append("unknown hook_mechanic")
    try:
        values["realism"] = int(values["realism"])
    except (KeyError, ValueError):
        errors.append("realism must be an integer")
    if not isinstance(values.get("realism"), int) or not 1 <= values["realism"] <= 5:
        errors.append("realism outside 1..5")
    return {"valid": not errors, "errors": errors, "fields": values}


def inspect_file(path):
    text = Path(path).read_text(encoding="utf-8")
    sections = _sections(text)
    if not sections:
        return {"n_sections": 0, "valid": False, "errors": ["no FORMAT CARD section found"], "card": None}
    if len(sections) > 1:
        return {"n_sections": len(sections), "valid": False, "errors": ["duplicate FORMAT CARD sections"], "card": None}
    card = parse_card(text)
    return {"n_sections": 1, "valid": card["valid"], "errors": card["errors"], "card": card}
