"""Shared fail-closed reader for runtime release state files."""

import re
from pathlib import Path


_RELEASE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ReleaseStateError(ValueError):
    """A runtime release state file is absent, unsafe, or malformed."""


def read_release_state(path: str | Path, *, label: str, required: bool = True) -> str | None:
    """Read exactly one canonical release digest without following symlinks."""
    state_path = Path(path)
    if state_path.is_symlink():
        raise ReleaseStateError(f"{label} state is a symlink")
    if not state_path.exists():
        if required:
            raise ReleaseStateError(f"{label} state is unavailable")
        return None
    try:
        lines = state_path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as error:
        raise ReleaseStateError(f"{label} state cannot be read") from error
    if len(lines) != 1 or _RELEASE_ID.fullmatch(lines[0]) is None:
        raise ReleaseStateError(f"{label} state is not one canonical digest line")
    return lines[0]
