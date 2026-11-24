from collections.abc import Callable
from pathlib import Path

import pytest

from agentctl.adapters import CursorAdapter


def _write_file(root: Path, relative_path: str, content: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path / "project"


@pytest.fixture
def adapter(home: Path) -> CursorAdapter:
    return CursorAdapter(home=home)


@pytest.fixture
def config_file_writer() -> Callable[[Path, str, str], Path]:
    return _write_file
