from collections.abc import Callable
from pathlib import Path

from agentctl.writes import RollbackIndex


def test_backup_copies_current_content(
    target: Path, rollback_index: RollbackIndex
) -> None:
    target.write_text("original", encoding="utf-8")

    record = rollback_index.backup(target)

    assert record is not None
    assert record.backup_path.read_text(encoding="utf-8") == "original"
    assert record.original_path == target


def test_backup_of_missing_file_is_noop(
    tmp_path: Path, rollback_index: RollbackIndex
) -> None:
    record = rollback_index.backup(tmp_path / "does-not-exist.json")

    assert record is None
    assert not rollback_index.backups


def test_repeated_backups_are_recorded_in_order(
    target: Path,
    rollback_index: RollbackIndex,
    write_and_backup: Callable[[Path, str], None],
) -> None:
    write_and_backup(target, "v1")
    write_and_backup(target, "v2")

    assert [
        b.backup_path.read_text(encoding="utf-8") for b in rollback_index.backups
    ] == ["v1", "v2"]


def test_restore_writes_back_the_most_recent_backup(
    target: Path,
    rollback_index: RollbackIndex,
    write_and_backup: Callable[[Path, str], None],
) -> None:
    write_and_backup(target, "v1")
    write_and_backup(target, "v2")
    target.write_text("v3 (unwanted write)", encoding="utf-8")

    restored = rollback_index.restore(target)

    assert restored is True
    assert target.read_text(encoding="utf-8") == "v2"


def test_restore_with_no_backup_returns_false(
    target: Path, rollback_index: RollbackIndex
) -> None:
    target.write_text("current", encoding="utf-8")

    restored = rollback_index.restore(target)

    assert restored is False
    assert target.read_text(encoding="utf-8") == "current"


def test_restore_all_undoes_every_write_this_session(
    tmp_path: Path,
    rollback_index: RollbackIndex,
    write_and_backup: Callable[[Path, str], None],
) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    write_and_backup(first, "a-original")
    write_and_backup(second, "b-original")
    first.write_text("a-modified", encoding="utf-8")
    second.write_text("b-modified", encoding="utf-8")

    rollback_index.restore_all()

    assert first.read_text(encoding="utf-8") == "a-original"
    assert second.read_text(encoding="utf-8") == "b-original"
    assert not rollback_index.backups
