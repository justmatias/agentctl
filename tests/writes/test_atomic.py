from pathlib import Path

import pytest

from agentctl.writes.atomic import atomic_write


def test_creates_file_with_content(target: Path) -> None:
    atomic_write(target, "hello")

    assert target.read_text() == "hello"


def test_overwrites_existing_content(target: Path) -> None:
    target.write_text("old")

    atomic_write(target, "new")

    assert target.read_text() == "new"


def test_creates_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "settings.json"

    atomic_write(target, "hello")

    assert target.read_text() == "hello"


def test_leaves_no_temp_file_behind(tmp_path: Path, target: Path) -> None:
    atomic_write(target, "hello")

    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.usefixtures("_fail_fsync")
def test_interrupted_write_leaves_original_file_untouched(
    tmp_path: Path, target: Path
) -> None:
    target.write_text("original")

    with pytest.raises(OSError, match="disk full"):
        atomic_write(target, "new content")

    assert target.read_text() == "original"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.usefixtures("_fail_fsync")
def test_interrupted_write_on_new_file_creates_nothing(
    tmp_path: Path, target: Path
) -> None:
    with pytest.raises(OSError, match="disk full"):
        atomic_write(target, "new content")

    assert not target.exists()
    assert not list(tmp_path.iterdir())
