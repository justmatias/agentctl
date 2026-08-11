from pathlib import Path

from agentctl.writes import RollbackIndex


class TestRollbackIndexBackup:
    @staticmethod
    def test_backup_copies_current_content(tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text("original", encoding="utf-8")
        index = RollbackIndex(tmp_path / "backups")

        record = index.backup(target)

        assert record is not None
        assert record.backup_path.read_text(encoding="utf-8") == "original"
        assert record.original_path == target

    @staticmethod
    def test_backup_of_missing_file_is_noop(tmp_path: Path) -> None:
        index = RollbackIndex(tmp_path / "backups")

        record = index.backup(tmp_path / "does-not-exist.json")

        assert record is None
        assert not index.backups

    @staticmethod
    def test_repeated_backups_are_recorded_in_order(tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        index = RollbackIndex(tmp_path / "backups")

        target.write_text("v1", encoding="utf-8")
        index.backup(target)
        target.write_text("v2", encoding="utf-8")
        index.backup(target)

        assert [
            b.backup_path.read_text(encoding="utf-8") for b in index.backups
        ] == ["v1", "v2"]


class TestRollbackIndexRestore:
    @staticmethod
    def test_restore_writes_back_the_most_recent_backup(tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        index = RollbackIndex(tmp_path / "backups")
        target.write_text("v1", encoding="utf-8")
        index.backup(target)
        target.write_text("v2", encoding="utf-8")
        index.backup(target)
        target.write_text("v3 (unwanted write)", encoding="utf-8")

        restored = index.restore(target)

        assert restored is True
        assert target.read_text(encoding="utf-8") == "v2"

    @staticmethod
    def test_restore_with_no_backup_returns_false(tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text("current", encoding="utf-8")
        index = RollbackIndex(tmp_path / "backups")

        restored = index.restore(target)

        assert restored is False
        assert target.read_text(encoding="utf-8") == "current"

    @staticmethod
    def test_restore_all_undoes_every_write_this_session(tmp_path: Path) -> None:
        first = tmp_path / "a.json"
        second = tmp_path / "b.json"
        index = RollbackIndex(tmp_path / "backups")
        first.write_text("a-original", encoding="utf-8")
        second.write_text("b-original", encoding="utf-8")
        index.backup(first)
        index.backup(second)
        first.write_text("a-modified", encoding="utf-8")
        second.write_text("b-modified", encoding="utf-8")

        index.restore_all()

        assert first.read_text(encoding="utf-8") == "a-original"
        assert second.read_text(encoding="utf-8") == "b-original"
        assert not index.backups
