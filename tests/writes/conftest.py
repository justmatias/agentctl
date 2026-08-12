from pathlib import Path

import pytest

from agentctl.writes import RollbackIndex


@pytest.fixture
def target(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"


@pytest.fixture
def rollback_index(tmp_path: Path) -> RollbackIndex:
    return RollbackIndex(tmp_path / "backups")
