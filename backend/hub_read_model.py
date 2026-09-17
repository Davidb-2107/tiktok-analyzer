"""Pure projection from verified snapshot runtime records to the Hub response."""

from collections.abc import Mapping

from media_store import validate_artifact_id


def project_runtime(runtime: Mapping[str, object]) -> dict[str, object]:
    cards = {
        (card["channel_id"], card["video_id"]): card
        for card in runtime["cards"]
        if "video_id" in card
    }
    assigned = {
        (mapping["channel_id"], mapping["video_id"]): mapping
        for mapping in runtime["mappings"]
        if mapping.get("status") == "assigned"
    }
    niches = []
    for channel in sorted(runtime["channels"], key=lambda item: item["channel_id"]):
        channel_id = channel["channel_id"]
        handle = channel["current_handle"]
        videos = []
        for key, mapping in sorted(assigned.items()):
            if key[0] != channel_id or key not in cards:
                continue
            card = cards[key]
            frame_id = card.get("frame_id")
            if frame_id is not None:
                validate_artifact_id(frame_id)
            videos.append(
                {
                    "source": "snapshot",
                    "id": key[1],
                    "titre": card.get("title"),
                    "chaine": handle,
                    "vues": card.get("views"),
                    "note": None,
                    "used": False,
                    "captured": None,
                    "transcript_ref": None,
                    "card_ref": None,
                    "thumb": frame_id,
                    "subformula_id": mapping["subformula_id"],
                }
            )
        niches.append(
            {
                "key": channel_id,
                "nom": handle,
                "projet_dir": None,
                "warnings": [],
                "sourcing": {"chaines": [handle], "videos": videos},
                "production": {"videos": []},
            }
        )
    return {"niches": niches}
