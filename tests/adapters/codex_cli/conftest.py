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


def codex_adapter_at(home: Path) -> CodexCliAdapter:
    """An adapter whose every machine-wide path stays inside `home`.

    Nothing a test runs may stat the developer's real `~/.codex` or `/etc/codex`,
    so both directories are always redirected into the scenario's home.
    """
    return CodexCliAdapter(
        codex_home=home / ".codex",
        system_config_directory=home / "system-config",
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


@pytest.fixture(
    params=[
        pytest.param(
            '[mcp_servers.broken]\nargs = ["--flag"]\n',
            id="mcp_server_without_command_or_url",
        ),
        pytest.param(
            'mcp_servers = { broken = "not-a-table" }\n',
            id="mcp_server_is_not_a_table",
        ),
        pytest.param(
            'mcp_servers = "not-a-table"\n', id="mcp_servers_is_not_a_table"
        ),
    ]
)
def malformed_config_path(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """A config file whose TOML parses but whose shape the adapter must reject."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(request.param)
    return config_path


@pytest.fixture(
    params=[
        pytest.param(
            '[mcp_servers.some-mcp]\ncommand = "npx"\nargs = ["-y", "some-mcp"]\n'
            '[mcp_servers.some-mcp.env]\nTOKEN = "secret"\n',
            id="nested_tables",
        ),
        pytest.param(
            'mcp_servers.some-mcp = { command = "npx", args = ["-y", "some-mcp"],'
            ' env = { TOKEN = "secret" } }\n',
            id="inline_tables",
        ),
        pytest.param(
            'mcp_servers.some-mcp.command = "npx"\n'
            'mcp_servers.some-mcp.args = ["-y", "some-mcp"]\n'
            'mcp_servers.some-mcp.env.TOKEN = "secret"\n',
            id="dotted_keys",
        ),
    ]
)
def equivalent_mcp_server_config_path(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Path:
    """One MCP server spelled three ways TOML allows, all meaning the same thing."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(request.param)
    return config_path


@pytest.fixture
def _write_machine_wide_configs(adapter: CodexCliAdapter) -> None:
    """Install the two administrator-owned config files the adapter reports."""
    for path in (adapter.managed_config_path, adapter.system_config_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('approval_policy = "on-request"\n')


@pytest.fixture(
    params=[
        pytest.param(
            (
                "remote-mcp",
                McpServerConfig(
                    url="https://example.com/mcp",
                    env={"TOKEN": "secret"},
                    headers={"X-Example-Region": "us-east-1"},
                ),
            ),
            id="remote-mcp",
        ),
        pytest.param(
            ("some-mcp", McpServerConfig(command="npx", args=["-y", "some-mcp"])),
            id="some-mcp",
        ),
    ]
)
def mcp_server_extension(request: pytest.FixtureRequest) -> Extension:
    """One MCP server extension per supported transport."""
    name, canonical_config = request.param
    return Extension(name=name, canonical_config=canonical_config)


@pytest.fixture(
    params=[
        pytest.param(
            (
                ExtensionType.MEMORY_FILE,
                WalkUpBehavior(
                    ascends=True,
                    stops_at=WalkUpStop.GIT_ROOT,
                    merge_semantics=MergeSemantics.CONCATENATE,
                ),
            ),
            id=ExtensionType.MEMORY_FILE.value,
        ),
        pytest.param(
            (
                ExtensionType.MCP_SERVER,
                WalkUpBehavior(
                    ascends=True,
                    stops_at=WalkUpStop.GIT_ROOT,
                    merge_semantics=MergeSemantics.OVERRIDE,
                ),
            ),
            id=ExtensionType.MCP_SERVER.value,
        ),
    ]
)
def expected_walk_up_behavior(
    request: pytest.FixtureRequest,
) -> tuple[ExtensionType, WalkUpBehavior]:
    """Each extension type paired with the walk-up contract Codex CLI declares.

    Codex layers both config and instructions from the project root down to the
    working directory, so every extension type ascends to the git root; only the
    merge semantics differ.
    """
    extension_type, behavior = request.param
    return extension_type, behavior


@pytest.fixture(params=["Darwin", "Windows", "Linux"])
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
        if request.param == "Windows"
        else adapter.system_config_directory
    )
    return directory / "managed_config.toml"


@pytest.fixture(params=[False, True], ids=["repository", "worktree"])
def nested_project_files(
    tmp_path: Path, request: pytest.FixtureRequest
) -> tuple[Path, list[Path]]:
    git_root = tmp_path / "repo"
    working_directory = git_root / "package" / "feature"
    working_directory.mkdir(parents=True)
    git_marker = git_root / ".git"
    if request.param:
        git_marker.write_text("gitdir: ../metadata/worktrees/repo\n")
    else:
        git_marker.mkdir()
        (git_marker / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / "AGENTS.md").write_text("Instructions above the Git root")

    files = [
        working_directory / ".codex" / "config.toml",
        git_root / ".codex" / "config.toml",
        working_directory / "AGENTS.md",
        working_directory.parent / "AGENTS.override.md",
        git_root / "AGENTS.md",
    ]
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Example instructions" if path.suffix == ".md" else "")
    return working_directory, files


@pytest.fixture(params=["", " \n"], ids=["empty", "whitespace"])
def _blank_global_override(
    global_and_project_adapter: CodexCliAdapter, request: pytest.FixtureRequest
) -> None:
    override = global_and_project_adapter.codex_home / "AGENTS.override.md"
    override.write_text(request.param)


@pytest.fixture
def project_with_blank_override(tmp_path: Path) -> Path:
    (tmp_path / "AGENTS.md").write_text("Project base instructions")
    (tmp_path / "AGENTS.override.md").touch()
    return tmp_path


@pytest.fixture
def instructions_file(tmp_path: Path) -> Path:
    path = tmp_path / "AGENTS.md"
    path.write_text("Project instructions")
    return path


@pytest.fixture
def _remove_instructions_after_read(
    instructions_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def read_instructions(path: Path, *, encoding: str, errors: str) -> str:
        with path.open(encoding=encoding, errors=errors) as stream:
            content = stream.read()
        if path == instructions_file:
            path.unlink()
        return content

    monkeypatch.setattr(Path, "read_text", read_instructions)
