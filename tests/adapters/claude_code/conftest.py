from pathlib import Path

import pytest

from agentctl.adapters import (
    ClaudeCodeAdapter,
    MergeSemantics,
    WalkUpBehavior,
    WalkUpStop,
)
from agentctl.domain import Extension, ExtensionType, McpServerConfig, Source
from tests.adapters.scenarios import copy_fixture_scenario

MALFORMED_SETTINGS_CONTENT = {
    "mcp_server_without_command": '{"mcpServers": {"broken": {"args": ["--flag"]}}}',
    "mcp_server_is_not_an_object": '{"mcpServers": {"broken": "not-an-object"}}',
    "document_is_not_an_object": "[1, 2, 3]",
}

MALFORMED_SKILL_CONTENT = {
    "no_frontmatter": "# No frontmatter here\n",
    "unparseable_frontmatter": "---\nname: [unclosed\n---\nBody\n",
    "frontmatter_is_not_a_mapping": "---\n- just\n- a\n- list\n---\nBody\n",
    "description_is_not_a_string": (
        "---\nname: broken-skill\ndescription: [not, a, string]\n---\nBody\n"
    ),
}

MCP_SERVER_CONFIGS = {
    "remote-mcp": McpServerConfig(
        url="https://example.com/mcp",
        env={"TOKEN": "secret"},
        headers={"Authorization": "Bearer secret"},
    ),
    "some-mcp": McpServerConfig(command="npx", args=["-y", "some-mcp"]),
}

EXPECTED_WALK_UP_BEHAVIORS = {
    ExtensionType.MEMORY_FILE: WalkUpBehavior(
        ascends=True,
        stops_at=WalkUpStop.FILESYSTEM_ROOT,
        merge_semantics=MergeSemantics.CONCATENATE,
    ),
    ExtensionType.MCP_SERVER: WalkUpBehavior(
        ascends=False, stops_at=WalkUpStop.NONE, merge_semantics=MergeSemantics.OVERRIDE
    ),
    ExtensionType.SKILL: WalkUpBehavior(
        ascends=False, stops_at=WalkUpStop.NONE, merge_semantics=MergeSemantics.OVERRIDE
    ),
}

EXPECTED_MANAGED_SETTINGS_PATHS = {
    "Darwin": Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
    "Windows": Path(r"C:\Program Files\ClaudeCode\managed-settings.json"),
    "Linux": Path("/etc/claude-code/managed-settings.json"),
}


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
    # The user-scoped auto-memory path is derived from the project's absolute
    # path, which only exists once the scenario has been copied into tmp_path.
    user_auto_memory_path = ClaudeCodeAdapter(home=home).auto_memory_path(project_root)
    user_auto_memory_path.parent.mkdir(parents=True)
    user_auto_memory_path.write_text(
        "# User auto-memory\n\n- Prefers tabs over spaces.\n"
    )
    return root


@pytest.fixture
def malformed_json_root(tmp_path: Path) -> Path:
    return copy_fixture_scenario(tmp_path, Source.CLAUDE_CODE, "malformed_json")


@pytest.fixture
def managed_settings_filename() -> str:
    return "managed-settings.json"


@pytest.fixture
def adapter(tmp_path: Path, managed_settings_filename: str) -> ClaudeCodeAdapter:
    """An adapter rooted at an empty home, for tests that supply their own files."""
    return ClaudeCodeAdapter(
        home=tmp_path, managed_settings_path=tmp_path / managed_settings_filename
    )


@pytest.fixture
def nothing_installed_adapter(
    nothing_installed_root: Path, managed_settings_filename: str
) -> ClaudeCodeAdapter:
    path = nothing_installed_root / "home"
    return ClaudeCodeAdapter(
        home=path, managed_settings_path=path / managed_settings_filename
    )


@pytest.fixture
def nothing_installed_project_root(nothing_installed_root: Path) -> Path:
    return nothing_installed_root / "project"


@pytest.fixture
def global_only_home(global_only_root: Path) -> Path:
    return global_only_root / "home"


@pytest.fixture
def global_only_adapter(
    global_only_home: Path, managed_settings_filename: str
) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(
        home=global_only_home,
        managed_settings_path=global_only_home / managed_settings_filename,
    )


@pytest.fixture
def global_and_project_adapter(
    global_and_project_root: Path, managed_settings_filename: str
) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(
        home=global_and_project_root / "home",
        managed_settings_path=global_and_project_root
        / "home"
        / managed_settings_filename,
    )


@pytest.fixture
def global_and_project_project_root(global_and_project_root: Path) -> Path:
    return global_and_project_root / "project"


@pytest.fixture
def malformed_json_home(malformed_json_root: Path) -> Path:
    return malformed_json_root / "home"


@pytest.fixture
def malformed_json_adapter(
    malformed_json_home: Path, managed_settings_filename: str
) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(
        home=malformed_json_home,
        managed_settings_path=malformed_json_home / managed_settings_filename,
    )


@pytest.fixture
def _write_managed_settings_file(
    tmp_path: Path, managed_settings_filename: str
) -> None:
    (tmp_path / managed_settings_filename).write_text("{}")


@pytest.fixture(
    params=[Path(".claude.json"), Path(".claude") / "settings.json"], ids=str
)
def malformed_json_path(
    request: pytest.FixtureRequest, malformed_json_home: Path
) -> Path:
    """Each global-scope JSON file the malformed_json scenario corrupts."""
    relative_path: Path = request.param
    return malformed_json_home / relative_path


@pytest.fixture(params=list(MALFORMED_SETTINGS_CONTENT))
def malformed_settings_path(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """A settings file whose JSON parses but whose shape the adapter must reject."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(MALFORMED_SETTINGS_CONTENT[request.param])
    return settings_path


@pytest.fixture(params=list(MALFORMED_SKILL_CONTENT))
def malformed_skill_path(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """A SKILL.md whose frontmatter the adapter must reject."""
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text(MALFORMED_SKILL_CONTENT[request.param])
    return skill_path


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
    """Each extension type paired with the walk-up contract Claude Code declares."""
    return request.param, EXPECTED_WALK_UP_BEHAVIORS[request.param]


@pytest.fixture(params=list(EXPECTED_MANAGED_SETTINGS_PATHS))
def expected_managed_settings_path(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Pretends to run on each operating system, yielding its managed settings path."""
    monkeypatch.setattr("platform.system", lambda: request.param)
    return EXPECTED_MANAGED_SETTINGS_PATHS[request.param]
