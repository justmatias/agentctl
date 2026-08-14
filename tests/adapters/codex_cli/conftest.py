from pathlib import Path

import pytest

from agentctl.adapters import (
    CodexCliAdapter,
    MergeSemantics,
    WalkUpBehavior,
    WalkUpStop,
)
from agentctl.domain import Extension, ExtensionType, McpServerConfig, Source
from tests.adapters.scenarios import copy_fixture_scenario

SYSTEM_CONFIG_DIRECTORY_NAME = "system-config"

MALFORMED_CONFIG_CONTENT = {
    "mcp_server_without_command_or_url": '[mcp_servers.broken]\nargs = ["--flag"]\n',
    "mcp_server_is_not_a_table": 'mcp_servers = { broken = "not-a-table" }\n',
    "mcp_servers_is_not_a_table": 'mcp_servers = "not-a-table"\n',
}

MCP_SERVER_CONFIGS = {
    "remote-mcp": McpServerConfig(
        url="https://example.com/mcp",
        env={"TOKEN": "secret"},
        headers={"X-Example-Region": "us-east-1"},
    ),
    "some-mcp": McpServerConfig(command="npx", args=["-y", "some-mcp"]),
}

# Codex layers both config and instructions from the project root down to the
# working directory, so every extension type ascends to the git root; only the
# merge semantics differ.
EXPECTED_WALK_UP_BEHAVIORS = {
    ExtensionType.MEMORY_FILE: WalkUpBehavior(
        ascends=True,
        stops_at=WalkUpStop.GIT_ROOT,
        merge_semantics=MergeSemantics.CONCATENATE,
    ),
    ExtensionType.MCP_SERVER: WalkUpBehavior(
        ascends=True,
        stops_at=WalkUpStop.GIT_ROOT,
        merge_semantics=MergeSemantics.OVERRIDE,
    ),
}

WINDOWS = "Windows"
OPERATING_SYSTEMS = ["Darwin", WINDOWS, "Linux"]


def codex_adapter_at(home: Path) -> CodexCliAdapter:
    """An adapter whose every machine-wide path stays inside `home`.

    Nothing a test runs may stat the developer's real `~/.codex` or `/etc/codex`,
    so both directories are always redirected into the scenario's home.
    """
    return CodexCliAdapter(
        codex_home=home / ".codex",
        system_config_directory=home / SYSTEM_CONFIG_DIRECTORY_NAME,
    )


@pytest.fixture
def adapter(tmp_path: Path) -> CodexCliAdapter:
    """An adapter rooted at an empty home, for tests that supply their own files."""
    return codex_adapter_at(tmp_path)


@pytest.fixture
def nothing_installed_root(tmp_path: Path) -> Path:
    """Neither a home nor a project directory has ever had Codex CLI touch it."""
    return tmp_path / "nothing_installed"


@pytest.fixture
def nothing_installed_adapter(nothing_installed_root: Path) -> CodexCliAdapter:
    return codex_adapter_at(nothing_installed_root / "home")


@pytest.fixture
def nothing_installed_project_root(nothing_installed_root: Path) -> Path:
    return nothing_installed_root / "project"


@pytest.fixture
def global_only_root(tmp_path: Path) -> Path:
    return copy_fixture_scenario(tmp_path, Source.CODEX_CLI, "global_only")


@pytest.fixture
def global_only_adapter(global_only_root: Path) -> CodexCliAdapter:
    return codex_adapter_at(global_only_root / "home")


@pytest.fixture
def global_and_project_root(tmp_path: Path) -> Path:
    return copy_fixture_scenario(tmp_path, Source.CODEX_CLI, "global_and_project")


@pytest.fixture
def global_and_project_adapter(global_and_project_root: Path) -> CodexCliAdapter:
    return codex_adapter_at(global_and_project_root / "home")


@pytest.fixture
def global_and_project_project_root(global_and_project_root: Path) -> Path:
    return global_and_project_root / "project"


@pytest.fixture
def malformed_toml_root(tmp_path: Path) -> Path:
    return copy_fixture_scenario(tmp_path, Source.CODEX_CLI, "malformed_toml")


@pytest.fixture
def malformed_toml_adapter(malformed_toml_root: Path) -> CodexCliAdapter:
    return codex_adapter_at(malformed_toml_root / "home")


@pytest.fixture(params=list(MALFORMED_CONFIG_CONTENT))
def malformed_config_path(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """A config file whose TOML parses but whose shape the adapter must reject."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(MALFORMED_CONFIG_CONTENT[request.param])
    return config_path


@pytest.fixture
def _write_machine_wide_configs(adapter: CodexCliAdapter) -> None:
    """Install the two administrator-owned config files the adapter reports."""
    for path in (adapter.managed_config_path, adapter.system_config_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('approval_policy = "on-request"\n')


@pytest.fixture(params=list(MCP_SERVER_CONFIGS))
def mcp_server_extension(request: pytest.FixtureRequest) -> Extension:
    """One MCP server extension per supported transport."""
    return Extension(
        name=request.param, canonical_config=MCP_SERVER_CONFIGS[request.param]
    )


@pytest.fixture(
    params=list(EXPECTED_WALK_UP_BEHAVIORS),
    ids=lambda extension_type: extension_type.value,
)
def expected_walk_up_behavior(
    request: pytest.FixtureRequest,
) -> tuple[ExtensionType, WalkUpBehavior]:
    """Each extension type paired with the walk-up contract Codex CLI declares."""
    return request.param, EXPECTED_WALK_UP_BEHAVIORS[request.param]


@pytest.fixture(params=OPERATING_SYSTEMS)
def expected_managed_config_path(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    adapter: CodexCliAdapter,
) -> Path:
    """Pretends to run on each operating system, yielding its managed config path.

    Codex keeps managed config in the system directory on Unix, but inside the
    Codex home on Windows.
    """
    monkeypatch.setattr("platform.system", lambda: request.param)
    directory = (
        adapter.codex_home
        if request.param == WINDOWS
        else adapter.system_config_directory
    )
    return directory / "managed_config.toml"
