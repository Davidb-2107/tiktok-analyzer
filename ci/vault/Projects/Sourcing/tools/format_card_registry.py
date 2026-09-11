"""Contract fixture for the canonical vault FORMAT CARD registry.

CI cannot depend on the developer's Windows vault path, so this stdlib-only
copy keeps the taxonomy and parse/inspection behavior used by Analyzer tests.
Synchronize these constants, regexes, errors, and return shapes with
``Projects/Sourcing/tools/format_card_registry.py`` in the vault whenever its
contract changes. Real vault data and unrelated CLI/write helpers stay out.
"""

from __future__ import annotations

import re
from pathlib import Path

STYLES = [
    "talking head",
    "POV skit",
    "AI animation",
    "screen recording",
    "b-roll + voiceover",
    "slideshow/photo",
    "vlog",
    "tutorial/demo",
    "reaction",
]
MECHANICS = [
    "shock/pattern-interrupt",
    "bold claim",
    "mid-action start",
    "curiosity gap",
    "direct address",
    "text-tease",
    "question",
]
REALISM_VALUES = {"1", "2", "3", "4", "5"}

_CARD_HEADER_RE = re.compile(r"^## FORMAT CARD.*$", re.M)
_SECTION_HEADER_RE = re.compile(r"^## .*$", re.M)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---(?:\s*\n|\Z)", re.S)


def _frontmatter_value(text: str, key: str) -> str | None:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    value_match = re.search(
        rf"^{re.escape(key)}:\s*([^#\n]+?)\s*$", match.group(1), re.M
    )
    if not value_match:
        return None
    return value_match.group(1).strip().strip("'\"") or None


def _field_values(card_text: str, label: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(
            rf"^- \*\*{re.escape(label)}:\*\*\s*(.+)$", card_text, re.M
        )
    ]


def _exact_token(raw: str) -> str:
    return raw.split("—", 1)[0].strip()


def parse_card(card_text: str) -> dict:
    errors = []
    fields = {}

    for label, canonical_key, known in (
        ("Video style", "video_style", STYLES),
        ("Hook mechanic", "hook_mechanic", MECHANICS),
    ):
        raw_values = _field_values(card_text, label)
        if not raw_values:
            errors.append(f"missing field: {label}")
            continue
        if len(raw_values) > 1:
            errors.append(f"duplicate field: {label}")
            continue
        token = _exact_token(raw_values[0])
        match = next((v for v in known if v.lower() == token.lower()), None)
        if match is None:
            errors.append(f"unknown value for {label}: {token!r}")
            continue
        fields[canonical_key] = match

    realism_values = _field_values(card_text, "Realism")
    if not realism_values:
        errors.append("missing field: Realism")
    elif len(realism_values) > 1:
        errors.append("duplicate field: Realism")
    else:
        token = _exact_token(realism_values[0])
        if token not in REALISM_VALUES:
            errors.append(f"unknown value for Realism: {token!r}")
        else:
            fields["realism"] = int(token)

    return {"fields": fields, "valid": not errors, "errors": errors}


def _find_card_section(text: str):
    headers = list(_CARD_HEADER_RE.finditer(text))
    if len(headers) != 1:
        return headers, None
    start = headers[0].start()
    next_header = _SECTION_HEADER_RE.search(text, headers[0].end())
    end = next_header.start() if next_header else len(text)
    return headers, (start, end)


def inspect_file(path: Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    is_transcript = _frontmatter_value(text, "video_url") is not None
    format_card_status = _frontmatter_value(text, "format_card_status")
    headers, span = _find_card_section(text)
    n_sections = len(headers)

    if n_sections == 0:
        return {
            "n_sections": 0,
            "valid": False,
            "errors": ["no FORMAT CARD section found"],
            "card": None,
            "format_card_status": format_card_status,
            "is_transcript": is_transcript,
        }
    if n_sections > 1:
        return {
            "n_sections": n_sections,
            "valid": False,
            "errors": ["duplicate FORMAT CARD sections"],
            "card": None,
            "format_card_status": format_card_status,
            "is_transcript": is_transcript,
        }

    start, end = span
    card = parse_card(text[start:end])
    return {
        "n_sections": 1,
        "valid": card["valid"],
        "errors": card["errors"],
        "card": card,
        "format_card_status": format_card_status,
        "is_transcript": is_transcript,
    }
