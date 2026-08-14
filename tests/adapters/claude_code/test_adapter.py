from pathlib import Path

import pytest

from agentctl.adapters import (
    ClaudeCodeAdapter,
    SourceAdapter,
    WalkUpBehavior,
    WorkflowTargetForm,
)
from agentctl.adapters.claude_code import default_managed_settings_path
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


def test_adapter_implements_the_source_adapter_protocol(
    adapter: ClaudeCodeAdapter,
) -> None:
    assert isinstance(adapter, SourceAdapter)
    assert adapter.source == Source.CLAUDE_CODE


def test_locate_global_config_finds_nothing_when_nothing_installed(
    nothing_installed_adapter: ClaudeCodeAdapter,
) -> None:
    assert nothing_installed_adapter.locate_global_config() == []


def test_locate_project_config_finds_nothing_when_nothing_installed(
    nothing_installed_adapter: ClaudeCodeAdapter,
    nothing_installed_project_root: Path,
) -> None:
    located = nothing_installed_adapter.locate_project_config(
        nothing_installed_project_root
    )

    assert located == []


def test_locate_global_config_finds_every_global_scope_file(
    global_only_adapter: ClaudeCodeAdapter, global_only_home: Path
) -> None:
    assert set(global_only_adapter.locate_global_config()) == {
        global_only_home / ".claude.json",
        global_only_home / ".claude" / "settings.json",
        global_only_home / ".claude" / "CLAUDE.md",
    }


def test_locate_project_config_finds_every_project_scope_file(
    global_and_project_adapter: ClaudeCodeAdapter,
    global_and_project_project_root: Path,
) -> None:
    project_root = global_and_project_project_root

    located = set(global_and_project_adapter.locate_project_config(project_root))

    assert located == {
        project_root / ".claude" / "settings.json",
        project_root / ".claude" / "settings.local.json",
        project_root / "CLAUDE.md",
        project_root / ".claude" / "memory" / "MEMORY.md",
        global_and_project_adapter.auto_memory_path(project_root),
        project_root / ".claude" / "skills" / "example-skill" / "SKILL.md",
    }


def test_parse_extracts_mcp_server_from_claude_json(
    global_only_adapter: ClaudeCodeAdapter, global_only_home: Path
) -> None:
    extensions = global_only_adapter.parse(global_only_home / ".claude.json")

    assert len(extensions) == 1
    extension = extensions[0]
    assert extension.name == "github-mcp"
    assert extension.origin_harness == Source.CLAUDE_CODE
    assert extension.type == ExtensionType.MCP_SERVER
    assert isinstance(extension.canonical_config, McpServerConfig)
    assert extension.canonical_config.command == "npx"
    assert extension.canonical_config.args == ["-y", "github-mcp"]


def test_parse_extracts_mcp_server_with_remote_transport(
    global_and_project_adapter: ClaudeCodeAdapter,
    global_and_project_project_root: Path,
) -> None:
    settings_path = global_and_project_project_root / ".claude" / "settings.json"

    extensions = global_and_project_adapter.parse(settings_path)

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, McpServerConfig)
    assert canonical.url == "https://example.com/mcp"
    assert canonical.headers == {"Authorization": "Bearer ${TOKEN}"}


def test_parse_settings_file_without_mcp_servers_yields_no_extensions(
    global_and_project_adapter: ClaudeCodeAdapter,
    global_and_project_project_root: Path,
) -> None:
    settings_path = global_and_project_project_root / ".claude" / "settings.local.json"

    assert not global_and_project_adapter.parse(settings_path)


def test_parse_extracts_project_instructions_file(
    global_and_project_adapter: ClaudeCodeAdapter,
    global_and_project_project_root: Path,
) -> None:
    extensions = global_and_project_adapter.parse(
        global_and_project_project_root / "CLAUDE.md"
    )

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, MemoryFileConfig)
    assert canonical.is_persistent_memory is False
    assert "Run `make test` before committing." in canonical.content


def test_parse_extracts_project_scoped_auto_memory(
    global_and_project_adapter: ClaudeCodeAdapter,
    global_and_project_project_root: Path,
) -> None:
    memory_path = global_and_project_project_root / ".claude" / "memory" / "MEMORY.md"

    extensions = global_and_project_adapter.parse(memory_path)

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, MemoryFileConfig)
    assert canonical.is_persistent_memory is True


def test_parse_extracts_user_scoped_auto_memory(
    global_and_project_adapter: ClaudeCodeAdapter,
    global_and_project_project_root: Path,
) -> None:
    auto_memory_path = global_and_project_adapter.auto_memory_path(
        global_and_project_project_root
    )

    extensions = global_and_project_adapter.parse(auto_memory_path)

    assert len(extensions) == 1
    canonical = extensions[0].canonical_config
    assert isinstance(canonical, MemoryFileConfig)
    assert canonical.is_persistent_memory is True
    assert "Prefers tabs over spaces." in canonical.content


def test_parse_extracts_skill_with_frontmatter_and_bundled_files(
    global_and_project_adapter: ClaudeCodeAdapter,
    global_and_project_project_root: Path,
) -> None:
    skill_path = (
        global_and_project_project_root
        / ".claude"
        / "skills"
        / "example-skill"
        / "SKILL.md"
    )

    extensions = global_and_project_adapter.parse(skill_path)

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


def test_parse_malformed_json_is_non_fatal(
    malformed_json_adapter: ClaudeCodeAdapter, malformed_json_path: Path
) -> None:
    assert not malformed_json_adapter.parse(malformed_json_path)


def test_parse_missing_file_is_non_fatal(
    adapter: ClaudeCodeAdapter, tmp_path: Path
) -> None:
    assert not adapter.parse(tmp_path / "does-not-exist.json")


def test_parse_skips_malformed_settings_content(
    adapter: ClaudeCodeAdapter, malformed_settings_path: Path
) -> None:
    assert not adapter.parse(malformed_settings_path)


def test_parse_unrecognized_file_type_returns_empty_list(
    adapter: ClaudeCodeAdapter, tmp_path: Path
) -> None:
    unknown_path = tmp_path / "notes.txt"
    unknown_path.write_text("just some notes")

    assert not adapter.parse(unknown_path)


def test_parse_skips_malformed_skill_content(
    adapter: ClaudeCodeAdapter, malformed_skill_path: Path
) -> None:
    assert not adapter.parse(malformed_skill_path)


def test_serialize_mcp_server_round_trips_through_parse(
    adapter: ClaudeCodeAdapter, tmp_path: Path, mcp_server_extension: Extension
) -> None:
    rendered = adapter.serialize(mcp_server_extension)
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(rendered)

    reparsed = adapter.parse(settings_path)

    assert len(reparsed) == 1
    assert reparsed[0].canonical_config == mcp_server_extension.canonical_config


def test_serialize_memory_file_returns_raw_content(adapter: ClaudeCodeAdapter) -> None:
    canonical = MemoryFileConfig(content="# Hello\n", is_persistent_memory=False)
    extension = Extension(name="CLAUDE.md", canonical_config=canonical)

    assert adapter.serialize(extension) == "# Hello\n"


def test_serialize_skill_round_trips_through_parse(
    adapter: ClaudeCodeAdapter, tmp_path: Path
) -> None:
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


def test_walk_up_behavior(
    adapter: ClaudeCodeAdapter,
    expected_walk_up_behavior: tuple[ExtensionType, WalkUpBehavior],
) -> None:
    extension_type, expected = expected_walk_up_behavior

    assert adapter.walk_up_behavior(extension_type) == expected


def test_capabilities_declares_all_three_extension_types(
    adapter: ClaudeCodeAdapter,
) -> None:
    capabilities = adapter.capabilities

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
    global_and_project_adapter: ClaudeCodeAdapter,
    global_and_project_project_root: Path,
) -> None:
    project_root = global_and_project_project_root

    chain = global_and_project_adapter.precedence_chain(project_root)

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


def test_precedence_chain_omits_local_and_project_layers_for_global_view(
    adapter: ClaudeCodeAdapter,
) -> None:
    chain = adapter.precedence_chain(None)

    scopes = {
        layer.scope for layer in chain.layers if isinstance(layer, ConsultedLayer)
    }
    assert Scope.LOCAL not in scopes
    assert Scope.PROJECT not in scopes
    assert Scope.USER in scopes


@pytest.mark.usefixtures("_write_managed_settings_file")
def test_precedence_chain_reports_managed_settings_existence(
    adapter: ClaudeCodeAdapter,
) -> None:
    chain = adapter.precedence_chain(None)

    managed_layer = next(
        layer
        for layer in chain.layers
        if isinstance(layer, ConsultedLayer) and layer.scope == Scope.MANAGED
    )
    assert managed_layer.exists is True
    assert managed_layer.resolves is True
    assert managed_layer.order_rank == 1


def test_precedence_chain_reports_agents_md_as_not_consulted(
    adapter: ClaudeCodeAdapter, tmp_path: Path
) -> None:
    chain = adapter.precedence_chain(tmp_path)

    not_consulted = [
        layer for layer in chain.layers if isinstance(layer, NotConsultedLayer)
    ]
    assert len(not_consulted) == 1
    assert not_consulted[0].file_path == str(tmp_path / "AGENTS.md")
    assert not_consulted[0].resolves is False


def test_default_managed_settings_path_is_operating_system_specific(
    expected_managed_settings_path: Path,
) -> None:
    assert default_managed_settings_path() == expected_managed_settings_path
