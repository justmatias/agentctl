import shutil
from pathlib import Path

import pytest

from agentctl.adapters import AdapterCapabilities
from agentctl.adapters.claude_code import auto_memory_path
from agentctl.adapters.fake import NullAdapter
from agentctl.domain import Source

_CLAUDE_CODE_FIXTURES_DIRECTORY = (
    Path(__file__).parent.parent / "fixtures" / "claude_code"
)


class MismatchedSourceAdapter(NullAdapter):
    """A NullAdapter whose declared capabilities.source disagrees with adapter.source."""

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            source=Source.CURSOR, extension_types=frozenset(), scopes=frozenset()
        )


@pytest.fixture
def mismatched_source_adapter() -> NullAdapter:
    return MismatchedSourceAdapter(Source.CLAUDE_CODE)


@pytest.fixture
def null_adapter() -> NullAdapter:
    return NullAdapter(Source.CLAUDE_CODE)


def _copy_claude_code_fixture_scenario(tmp_path: Path, scenario_name: str) -> Path:
    destination = tmp_path / scenario_name
    shutil.copytree(_CLAUDE_CODE_FIXTURES_DIRECTORY / scenario_name, destination)
    return destination


@pytest.fixture
def nothing_installed_root(tmp_path: Path) -> Path:
    """Neither a home nor a project directory has ever had Claude Code touch it."""
    return tmp_path / "nothing_installed"


@pytest.fixture
def global_only_root(tmp_path: Path) -> Path:
    return _copy_claude_code_fixture_scenario(tmp_path, "global_only")


@pytest.fixture
def global_and_project_root(tmp_path: Path) -> Path:
    root = _copy_claude_code_fixture_scenario(tmp_path, "global_and_project")
    project_root = root / "project"
    home = root / "home"
    user_auto_memory_path = auto_memory_path(home, project_root)
    user_auto_memory_path.parent.mkdir(parents=True)
    user_auto_memory_path.write_text(
        "# User auto-memory\n\n- Prefers tabs over spaces.\n"
    )
    return root


@pytest.fixture
def malformed_json_root(tmp_path: Path) -> Path:
    return _copy_claude_code_fixture_scenario(tmp_path, "malformed_json")
