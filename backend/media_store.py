"""Filesystem adapter for separately retained Hub frame artifacts."""

from pathlib import Path

from publication.media import MEDIA_EXTENSIONS, validate_artifact_id as _validate_artifact_id


_IMAGE_EXTENSIONS = MEDIA_EXTENSIONS


def validate_artifact_id(frame_id: str) -> str:
    try:
        return _validate_artifact_id(frame_id)
    except ValueError as error:
        raise ValueError("frame_id must be an opaque artifact ID") from error


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
