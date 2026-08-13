from pathlib import Path

import pytest

from agentctl.adapters import SourceAdapter
from agentctl.adapters.claude_code import ClaudeCodeAdapter
from agentctl.adapters.protocol import MergeSemantics, WalkUpStop, WorkflowTargetForm
from agentctl.domain import (
    ConsultedLayer,
    Extension,
    ExtensionType,
    McpServerConfig,
    MemoryFileConfig,
    NotConsultedLayer,
    Scope,
    SkillConfig,
    Source,
)


def test_adapter_implements_the_source_adapter_protocol() -> None:
    assert isinstance(ClaudeCodeAdapter(), SourceAdapter)
    assert ClaudeCodeAdapter().source == Source.CLAUDE_CODE


def test_locate_global_config_finds_nothing_when_nothing_installed(
    nothing_installed_root: Path,
) -> None:
    adapter = ClaudeCodeAdapter(home=nothing_installed_root / "home")

    assert adapter.locate_global_config() == []


def test_locate_project_config_finds_nothing_when_nothing_installed(
    nothing_installed_root: Path,
) -> None:
    adapter = ClaudeCodeAdapter(home=nothing_installed_root / "home")

    assert adapter.locate_project_config(nothing_installed_root / "project") == []


def test_locate_global_config_finds_every_global_scope_file(
    global_only_root: Path,
) -> None:
    home = global_only_root / "home"
    adapter = ClaudeCodeAdapter(home=home)

    assert set(adapter.locate_global_config()) == {
        home / ".claude.json",
        home / ".claude" / "settings.json",
        home / ".claude" / "CLAUDE.md",
    }


def test_locate_project_config_finds_every_project_scope_file(
    global_and_project_root: Path,
) -> None:
    home = global_and_project_root / "home"
    project_root = global_and_project_root / "project"
    adapter = ClaudeCodeAdapter(home=home)

    located = set(adapter.locate_project_config(project_root))

    assert located == {
        project_root / ".claude" / "settings.json",
        project_root / ".claude" / "settings.local.json",
        project_root / "CLAUDE.md",
        project_root / ".claude" / "memory" / "MEMORY.md",
        adapter.auto_memory_path(project_root),
        project_root / ".claude" / "skills" / "example-skill" / "SKILL.md",
    }


def test_parse_extracts_mcp_server_from_claude_json(global_only_root: Path) -> None:
    home = global_only_root / "home"
    adapter = ClaudeCodeAdapter(home=home)

    extensions = adapter.parse(home / ".claude.json")

    assert len(extensions) == 1
    extension = extensions[0]
    assert extension.name == "github-mcp"
    assert extension.origin_harness == Source.CLAUDE_CODE
    assert extension.type == ExtensionType.MCP_SERVER
    assert isinstance(extension.canonical_config, McpServerConfig)
    assert extension.canonical_config.command == "npx"
    assert extension.canonical_config.args == ["-y", "github-mcp"]


def test_parse_extracts_mcp_server_with_remote_transport(
    global_and_project_root: Path,
) -> None:
    project_root = global_and_project_root / "project"
    adapter = ClaudeCodeAdapter(home=global_and_project_root / "home")

    extensions = adapter.parse(project_root / ".claude" / "settings.json")

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, McpServerConfig)
    assert canonical.url == "https://example.com/mcp"
    assert canonical.headers == {"Authorization": "Bearer ${TOKEN}"}


def test_parse_settings_file_without_mcp_servers_yields_no_extensions(
    global_and_project_root: Path,
) -> None:
    project_root = global_and_project_root / "project"
    adapter = ClaudeCodeAdapter(home=global_and_project_root / "home")

    extensions = adapter.parse(project_root / ".claude" / "settings.local.json")

    assert not extensions


def test_parse_extracts_project_instructions_file(
    global_and_project_root: Path,
) -> None:
    project_root = global_and_project_root / "project"
    adapter = ClaudeCodeAdapter(home=global_and_project_root / "home")

    extensions = adapter.parse(project_root / "CLAUDE.md")

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, MemoryFileConfig)
    assert canonical.is_persistent_memory is False
    assert "Run `make test` before committing." in canonical.content


def test_parse_extracts_project_scoped_auto_memory(
    global_and_project_root: Path,
) -> None:
    project_root = global_and_project_root / "project"
    adapter = ClaudeCodeAdapter(home=global_and_project_root / "home")

    extensions = adapter.parse(project_root / ".claude" / "memory" / "MEMORY.md")

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, MemoryFileConfig)
    assert canonical.is_persistent_memory is True


def test_parse_extracts_user_scoped_auto_memory(global_and_project_root: Path) -> None:
    project_root = global_and_project_root / "project"
    home = global_and_project_root / "home"
    adapter = ClaudeCodeAdapter(home=home)

    extensions = adapter.parse(adapter.auto_memory_path(project_root))

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, MemoryFileConfig)
    assert canonical.is_persistent_memory is True
    assert "Prefers tabs over spaces." in canonical.content


def test_parse_extracts_skill_with_frontmatter_and_bundled_files(
    global_and_project_root: Path,
) -> None:
    project_root = global_and_project_root / "project"
    adapter = ClaudeCodeAdapter(home=global_and_project_root / "home")
    skill_path = project_root / ".claude" / "skills" / "example-skill" / "SKILL.md"

    extensions = adapter.parse(skill_path)

    assert len(extensions) == 1
    extension = extensions[0]
    assert extension.name == "example-skill"
    canonical = extension.canonical_config
    assert isinstance(canonical, SkillConfig)
    assert (
        canonical.description
        == "An example skill used for Claude Code adapter fixture testing."
    )
    assert "Do the example thing" in canonical.body
    assert canonical.bundled_files == ["reference.md"]


@pytest.mark.parametrize(
    "relative_path",
    [Path(".claude.json"), Path(".claude") / "settings.json"],
)
def test_parse_malformed_json_is_non_fatal(
    malformed_json_root: Path, relative_path: Path
) -> None:
    home = malformed_json_root / "home"
    adapter = ClaudeCodeAdapter(home=home)

    assert not adapter.parse(home / relative_path)


def test_parse_missing_file_is_non_fatal(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter(home=tmp_path)

    assert not adapter.parse(tmp_path / "does-not-exist.json")


@pytest.mark.parametrize(
    "content",
    [
        '{"mcpServers": {"broken": {"args": ["--flag"]}}}',
        '{"mcpServers": {"broken": "not-an-object"}}',
        "[1, 2, 3]",
    ],
)
def test_parse_skips_malformed_settings_content(tmp_path: Path, content: str) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(content)
    adapter = ClaudeCodeAdapter(home=tmp_path)

    assert not adapter.parse(settings_path)


def test_parse_unrecognized_file_type_returns_empty_list(tmp_path: Path) -> None:
    unknown_path = tmp_path / "notes.txt"
    unknown_path.write_text("just some notes")
    adapter = ClaudeCodeAdapter(home=tmp_path)

    assert not adapter.parse(unknown_path)


@pytest.mark.parametrize(
    "content",
    [
        "# No frontmatter here\n",
        "---\nname: [unclosed\n---\nBody\n",
        "---\n- just\n- a\n- list\n---\nBody\n",
        "---\nname: broken-skill\ndescription: [not, a, string]\n---\nBody\n",
    ],
)
def test_parse_skips_malformed_skill_content(tmp_path: Path, content: str) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text(content)
    adapter = ClaudeCodeAdapter(home=tmp_path)

    assert not adapter.parse(skill_path)


@pytest.mark.parametrize(
    ("name", "canonical"),
    [
        (
            "remote-mcp",
            McpServerConfig(
                url="https://example.com/mcp",
                env={"TOKEN": "secret"},
                headers={"Authorization": "Bearer secret"},
            ),
        ),
        ("some-mcp", McpServerConfig(command="npx", args=["-y", "some-mcp"])),
    ],
)
def test_serialize_mcp_server_round_trips_through_parse(
    tmp_path: Path, name: str, canonical: McpServerConfig
) -> None:
    adapter = ClaudeCodeAdapter(home=tmp_path)
    extension = Extension(name=name, canonical_config=canonical)

    rendered = adapter.serialize(extension)
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(rendered)
    reparsed = adapter.parse(settings_path)

    assert len(reparsed) == 1
    assert reparsed[0].canonical_config == canonical


def test_serialize_memory_file_returns_raw_content() -> None:
    adapter = ClaudeCodeAdapter()
    canonical = MemoryFileConfig(content="# Hello\n", is_persistent_memory=False)
    extension = Extension(name="CLAUDE.md", canonical_config=canonical)

    assert adapter.serialize(extension) == "# Hello\n"


def test_serialize_skill_round_trips_through_parse(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter(home=tmp_path)
    canonical = SkillConfig(description="Does a thing.", body="# Body\n\nDetails.")
    extension = Extension(name="some-skill", canonical_config=canonical)

    rendered = adapter.serialize(extension)
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text(rendered)
    reparsed = adapter.parse(skill_path)

    assert len(reparsed) == 1
    assert reparsed[0].name == "some-skill"
    reparsed_canonical = reparsed[0].canonical_config
    assert isinstance(reparsed_canonical, SkillConfig)
    assert reparsed_canonical.description == "Does a thing."
    assert reparsed_canonical.body == "# Body\n\nDetails."


@pytest.mark.parametrize(
    ("extension_type", "expected_ascends", "expected_stops_at", "expected_merge_semantics"),
    [
        (
            ExtensionType.MEMORY_FILE,
            True,
            WalkUpStop.FILESYSTEM_ROOT,
            MergeSemantics.CONCATENATE,
        ),
        (
            ExtensionType.MCP_SERVER,
            False,
            WalkUpStop.NONE,
            MergeSemantics.OVERRIDE,
        ),
        (
            ExtensionType.SKILL,
            False,
            WalkUpStop.NONE,
            MergeSemantics.OVERRIDE,
        ),
    ],
)
def test_walk_up_behavior(
    extension_type: ExtensionType,
    expected_ascends: bool,
    expected_stops_at: WalkUpStop,
    expected_merge_semantics: MergeSemantics,
) -> None:
    adapter = ClaudeCodeAdapter()

    behavior = adapter.walk_up_behavior(extension_type)

    assert behavior.ascends is expected_ascends
    assert behavior.stops_at == expected_stops_at
    assert behavior.merge_semantics == expected_merge_semantics


def test_capabilities_declares_all_three_extension_types() -> None:
    capabilities = ClaudeCodeAdapter().capabilities

    assert capabilities.source == Source.CLAUDE_CODE
    assert capabilities.extension_types == frozenset({
        ExtensionType.MCP_SERVER,
        ExtensionType.MEMORY_FILE,
        ExtensionType.SKILL,
    })
    # Claude Code's 5-layer precedence chain (ROADMAP.md PR 1.1) exercises every
    # Scope value, so this is equivalent to listing them out without duplicating
    # the adapter's own literal (pylint duplicate-code).
    assert capabilities.scopes == frozenset(Scope)
    assert capabilities.workflow_target_forms == frozenset({WorkflowTargetForm.SKILL})


def test_precedence_chain_reports_five_layer_scope_for_a_project(
    global_and_project_root: Path,
) -> None:
    home = global_and_project_root / "home"
    project_root = global_and_project_root / "project"
    managed_settings_path = home / "managed-settings.json"
    adapter = ClaudeCodeAdapter(home=home, managed_settings_path=managed_settings_path)

    chain = adapter.precedence_chain(project_root)

    assert chain.source == Source.CLAUDE_CODE
    consulted = [layer for layer in chain.layers if isinstance(layer, ConsultedLayer)]
    assert [
        layer.scope for layer in sorted(consulted, key=lambda layer: layer.order_rank)
    ] == [
        Scope.MANAGED,
        Scope.GLOBAL,
        Scope.LOCAL,
        Scope.PROJECT,
        Scope.USER,
    ]
    local_layer = next(layer for layer in consulted if layer.scope == Scope.LOCAL)
    assert local_layer.file_path == str(
        project_root / ".claude" / "settings.local.json"
    )
    assert local_layer.exists is True
    project_layer = next(layer for layer in consulted if layer.scope == Scope.PROJECT)
    assert project_layer.file_path == str(project_root / ".claude" / "settings.json")
    assert project_layer.exists is True
    cli_arg_layer = next(layer for layer in consulted if layer.scope == Scope.GLOBAL)
    assert cli_arg_layer.exists is False
    assert cli_arg_layer.resolves is False


def test_precedence_chain_omits_local_and_project_layers_for_global_view() -> None:
    adapter = ClaudeCodeAdapter()

    chain = adapter.precedence_chain(None)

    scopes = {
        layer.scope for layer in chain.layers if isinstance(layer, ConsultedLayer)
    }
    assert Scope.LOCAL not in scopes
    assert Scope.PROJECT not in scopes
    assert Scope.USER in scopes


def test_precedence_chain_reports_managed_settings_existence(tmp_path: Path) -> None:
    managed_settings_path = tmp_path / "managed-settings.json"
    managed_settings_path.write_text("{}")
    adapter = ClaudeCodeAdapter(
        home=tmp_path, managed_settings_path=managed_settings_path
    )

    chain = adapter.precedence_chain(None)

    managed_layer = next(
        layer
        for layer in chain.layers
        if isinstance(layer, ConsultedLayer) and layer.scope == Scope.MANAGED
    )
    assert managed_layer.exists is True
    assert managed_layer.resolves is True
    assert managed_layer.order_rank == 1


def test_precedence_chain_reports_agents_md_as_not_consulted(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter(home=tmp_path)

    chain = adapter.precedence_chain(tmp_path)

    not_consulted = [
        layer for layer in chain.layers if isinstance(layer, NotConsultedLayer)
    ]
    assert len(not_consulted) == 1
    assert not_consulted[0].file_path == str(tmp_path / "AGENTS.md")
    assert not_consulted[0].resolves is False


@pytest.mark.parametrize(
    ("operating_system", "expected_path"),
    [
        ("Darwin", "/Library/Application Support/ClaudeCode/managed-settings.json"),
        ("Windows", r"C:\Program Files\ClaudeCode\managed-settings.json"),
        ("Linux", "/etc/claude-code/managed-settings.json"),
    ],
)
def test_default_managed_settings_path_is_operating_system_specific(
    monkeypatch: pytest.MonkeyPatch, operating_system: str, expected_path: str
) -> None:
    monkeypatch.setattr("platform.system", lambda: operating_system)

    assert ClaudeCodeAdapter.default_managed_settings_path() == Path(expected_path)
