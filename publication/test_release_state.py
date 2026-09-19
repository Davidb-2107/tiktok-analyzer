import os

import pytest

from publication.release_state import ReleaseStateError, read_release_state


RELEASE_ID = "sha256:" + "a" * 64


def test_read_release_state_accepts_one_canonical_digest_line(tmp_path):
    path = tmp_path / "active-release"
    path.write_bytes((RELEASE_ID + "\n").encode("ascii"))

    assert read_release_state(path, label="active") == RELEASE_ID


def test_read_release_state_distinguishes_optional_absence(tmp_path):
    path = tmp_path / "active-release"

    assert read_release_state(path, label="active", required=False) is None
    with pytest.raises(ReleaseStateError, match="active state is unavailable"):
        read_release_state(path, label="active")


@pytest.mark.parametrize("contents", [b"", (RELEASE_ID + "\nextra\n").encode("ascii"), b"sha256:UPPER\n"])
def test_read_release_state_rejects_noncanonical_contents(tmp_path, contents):
    path = tmp_path / "active-release"
    path.write_bytes(contents)

    with pytest.raises(ReleaseStateError, match="active state"):
        read_release_state(path, label="active")


def test_read_release_state_rejects_symlinks(tmp_path):
    target = tmp_path / "target"
    target.write_text(RELEASE_ID + "\n", encoding="ascii")
    path = tmp_path / "active-release"
    try:
        os.symlink(target, path)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable")

    with pytest.raises(ReleaseStateError, match="active state is a symlink"):
        read_release_state(path, label="active")


def test_read_release_state_rejects_unreadable_entries(tmp_path):
    path = tmp_path / "active-release"
    path.mkdir()

    with pytest.raises(ReleaseStateError, match="active state cannot be read"):
        read_release_state(path, label="active")
