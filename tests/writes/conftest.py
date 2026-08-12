import os
from collections.abc import Callable
from pathlib import Path

import pytest

from agentctl.writes import RollbackIndex


@pytest.fixture
def target(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"


@pytest.fixture
def rollback_index(tmp_path: Path) -> RollbackIndex:
    return RollbackIndex(tmp_path / "backups")


@pytest.fixture
def write_and_backup(rollback_index: RollbackIndex) -> Callable[[Path, str], None]:
    def _write_and_backup(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        rollback_index.backup(path)

    return _write_and_backup


@pytest.fixture
def _fail_fsync(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_fsync(fd: int) -> None:
        del fd
        raise OSError("disk full")

    monkeypatch.setattr(os, "fsync", failing_fsync)
