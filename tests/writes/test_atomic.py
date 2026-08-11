from pathlib import Path

import pytest

from agentctl.writes import atomic
from agentctl.writes.atomic import atomic_write


class TestAtomicWrite:
    @staticmethod
    def test_creates_file_with_content(tmp_path: Path) -> None:
        target = tmp_path / "settings.json"

        atomic_write(target, "hello")

        assert target.read_text() == "hello"

    @staticmethod
    def test_overwrites_existing_content(tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text("old")

        atomic_write(target, "new")

        assert target.read_text() == "new"

    @staticmethod
    def test_creates_parent_directories(tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "settings.json"

        atomic_write(target, "hello")

        assert target.read_text() == "hello"

    @staticmethod
    def test_leaves_no_temp_file_behind(tmp_path: Path) -> None:
        target = tmp_path / "settings.json"

        atomic_write(target, "hello")

        assert list(tmp_path.iterdir()) == [target]

    @staticmethod
    def test_interrupted_write_leaves_original_file_untouched(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "settings.json"
        target.write_text("original")

        def failing_write(tmp_path_arg: Path, content: str, encoding: str) -> None:
            del content
            tmp_path_arg.write_text("partial", encoding=encoding)
            raise OSError("disk full")

        monkeypatch.setattr(atomic, "_write_to_temp", failing_write)

        with pytest.raises(OSError, match="disk full"):
            atomic_write(target, "new content")

        assert target.read_text() == "original"
        assert list(tmp_path.iterdir()) == [target]

    @staticmethod
    def test_interrupted_write_on_new_file_creates_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "settings.json"

        def failing_write(tmp_path_arg: Path, content: str, encoding: str) -> None:
            del tmp_path_arg, content, encoding
            raise OSError("disk full")

        monkeypatch.setattr(atomic, "_write_to_temp", failing_write)

        with pytest.raises(OSError, match="disk full"):
            atomic_write(target, "new content")

        assert not target.exists()
        assert not list(tmp_path.iterdir())
