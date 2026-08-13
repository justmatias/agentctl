import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from agentctl.adapters import (
    AdapterCapabilities,
    ClaudeCodeAdapter,
    NullAdapter,
    SourceAdapter,
)
from agentctl.domain import (
    CanonicalConfig,
    ExtensionType,
    McpServerConfig,
    MemoryFileConfig,
    PrecedenceChain,
    SkillConfig,
    Source,
)

FIXTURES_DIRECTORY = Path(__file__).parent.parent / "fixtures"


AdapterFactory = Callable[[Path], SourceAdapter]

# Every real adapter, built against a throwaway home directory so the contract
# suite never reads the developer's own config. Registering a new adapter here
# is all it takes for test_adapter_contract.py to hold it to the SourceAdapter
# contract.
ADAPTER_FACTORIES: dict[Source, AdapterFactory] = {
    Source.CLAUDE_CODE: lambda home: ClaudeCodeAdapter(
        home=home, managed_settings_path=home / "managed-settings.json"
    ),
}


def copy_fixture_scenario(tmp_path: Path, source: Source, scenario_name: str) -> Path:
    destination = tmp_path / scenario_name
    shutil.copytree(FIXTURES_DIRECTORY / source.value / scenario_name, destination)
    return destination


@pytest.fixture(params=list(ADAPTER_FACTORIES), ids=lambda source: source.value)
def adapter(request: pytest.FixtureRequest, tmp_path: Path) -> SourceAdapter:
    """Each registered adapter in turn, rooted at an empty home directory."""
    home = tmp_path / "home"
    home.mkdir()
    return ADAPTER_FACTORIES[request.param](home)


@pytest.fixture
def mismatched_source_adapter() -> NullAdapter:
    class MismatchedSourceAdapter(NullAdapter):
        """A NullAdapter whose declared capabilities.source disagrees with adapter.source."""

        @property
        def capabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                source=Source.CURSOR, extension_types=frozenset(), scopes=frozenset()
            )

    return MismatchedSourceAdapter(Source.CLAUDE_CODE)


@pytest.fixture
def null_adapter() -> NullAdapter:
    return NullAdapter(Source.CLAUDE_CODE)


@pytest.fixture
def empty_project_root(tmp_path: Path) -> Path:
    """A project directory no harness has ever written to."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    return project_root


@pytest.fixture
def canonical_configs() -> dict[ExtensionType, CanonicalConfig]:
    # One canonical config per extension type, so the contract suite can ask every
    # adapter to serialize each type it claims to support.
    return {
        ExtensionType.MCP_SERVER: McpServerConfig(
            command="npx", args=["-y", "github-mcp"]
        ),
        ExtensionType.MEMORY_FILE: MemoryFileConfig(
            content="# Project notes\n\n- Prefers tabs.\n", is_persistent_memory=False
        ),
        ExtensionType.SKILL: SkillConfig(
            description="Formats the codebase.",
            body="Run the formatter, then the linter.",
        ),
    }


@pytest.fixture(params=["global_view", "project_view"])
def precedence_chain(
    request: pytest.FixtureRequest, adapter: SourceAdapter, empty_project_root: Path
) -> PrecedenceChain:
    """The chain an adapter reports, in both the global and project-scoped views."""
    project_root = None if request.param == "global_view" else empty_project_root
    return adapter.precedence_chain(project_root)


@pytest.fixture
def nothing_installed_root(tmp_path: Path) -> Path:
    """Neither a home nor a project directory has ever had Claude Code touch it."""
    return tmp_path / "nothing_installed"


@pytest.fixture
def global_only_root(tmp_path: Path) -> Path:
    return copy_fixture_scenario(tmp_path, Source.CLAUDE_CODE, "global_only")


@pytest.fixture
def global_and_project_root(tmp_path: Path) -> Path:
    root = copy_fixture_scenario(tmp_path, Source.CLAUDE_CODE, "global_and_project")
    project_root = root / "project"
    home = root / "home"
    user_auto_memory_path = ClaudeCodeAdapter(home=home).auto_memory_path(project_root)
    user_auto_memory_path.parent.mkdir(parents=True)
    user_auto_memory_path.write_text(
        "# User auto-memory\n\n- Prefers tabs over spaces.\n"
    )
    return root


@pytest.fixture
def malformed_json_root(tmp_path: Path) -> Path:
    return copy_fixture_scenario(tmp_path, Source.CLAUDE_CODE, "malformed_json")
