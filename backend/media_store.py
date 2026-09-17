"""Filesystem adapter for separately retained Hub frame artifacts."""

import re
from pathlib import Path


_ARTIFACT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def validate_artifact_id(frame_id: str) -> str:
    if not isinstance(frame_id, str) or _ARTIFACT_ID.fullmatch(frame_id) is None:
        raise ValueError("frame_id must be an opaque artifact ID")
    return frame_id


class MediaStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def resolve(self, frame_id: str) -> Path:
        artifact_id = validate_artifact_id(frame_id)
        matches = [
            candidate
            for extension in _IMAGE_EXTENSIONS
            if (candidate := self.root / f"{artifact_id}{extension}").is_file()
        ]
        if len(matches) != 1:
            raise FileNotFoundError(artifact_id)
        return matches[0]
