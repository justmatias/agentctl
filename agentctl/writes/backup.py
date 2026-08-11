"""Timestamped backups with a session-scoped rollback index (SPECS.md §7.11, §11)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .atomic import atomic_write


@dataclass(frozen=True)
class Backup:
    original_path: Path
    backup_path: Path
    created_at: datetime


class RollbackIndex:
    """Records every backup made this session and can undo them, in order.

    Backups are plain timestamped copies under `backup_dir` — nothing here
    is written back to `original_path` until `restore`/`restore_all` is
    called, and nothing is ever deleted from `original_path`'s directory.
    """

    def __init__(self, backup_dir: Path | str) -> None:
        self._backup_dir = Path(backup_dir)
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._backups: list[Backup] = []

    @property
    def backups(self) -> list[Backup]:
        return list(self._backups)

    def backup(self, path: Path | str) -> Backup | None:
        """Snapshot `path` before it gets overwritten. No-op if it doesn't exist yet."""
        path = Path(path)
        if not path.exists():
            return None
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        backup_path = self._backup_dir / f"{path.name}.{timestamp}.{len(self._backups)}.bak"
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        record = Backup(
            original_path=path, backup_path=backup_path, created_at=datetime.now(UTC)
        )
        self._backups.append(record)
        return record

    def restore(self, path: Path | str) -> bool:
        """Restore `path`'s most recent backup. Returns False if none exists."""
        path = Path(path)
        for record in reversed(self._backups):
            if record.original_path == path:
                atomic_write(path, record.backup_path.read_text(encoding="utf-8"))
                return True
        return False

    def restore_all(self) -> None:
        """Undo every write this session, most recent first, then clear the index."""
        for record in reversed(self._backups):
            atomic_write(record.original_path, record.backup_path.read_text(encoding="utf-8"))
        self._backups.clear()
