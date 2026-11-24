from collections.abc import Callable
from pathlib import Path

from agentctl.adapters import CursorAdapter, DotAgentsAdapter, MergeSemantics
from agentctl.domain import (
    ConsultedLayer,
    ExtensionType,
    McpServerConfig,
    MemoryFileConfig,
    NotConsultedLayer,
    Scope,
    SkillConfig,
    Source,
    UnconfirmedLayer,
)


def test_canonical_extensions_when_only_global_config_exists(
    adapter: CursorAdapter,
    home: Path,
    config_file_writer: Callable[[Path, str, str], Path],
) -> None:
    config_file_writer(
        home,
        ".cursor/mcp.json",
        '{"mcpServers":{"remote":{"url":"https://example.com/mcp",'
        '"headers":{"X-Test":"value"}}}}',
    )
    skill = config_file_writer(
        home,
        ".cursor/skills/quality/inspect/SKILL.md",
        "---\nname: inspect\n---\nInspect files.\n",
    )
    config_file_writer(skill.parent, "notes.md", "Reference")
    assert {
        (extension.origin_harness, extension.name): extension.canonical_config
        for path in adapter.locate_global_config()
        for extension in adapter.parse(path)
    } == {
        (Source.CURSOR, "remote"): McpServerConfig(
            url="https://example.com/mcp", headers={"X-Test": "value"}
        ),
        (Source.CURSOR, "inspect"): SkillConfig(
            description="", body="Inspect files.", bundled_files=["notes.md"]
        ),
    }


def test_project_extensions_when_project_has_cursor_config(
    adapter: CursorAdapter,
    project: Path,
    config_file_writer: Callable[[Path, str, str], Path],
) -> None:
    config = config_file_writer(
        project, ".cursor/mcp.json", '{"mcpServers":{"local":{"command":"example"}}}'
    )
    instructions = {
        config_file_writer(project, ".cursorrules", "Legacy"): "Legacy",
        config_file_writer(project, "AGENTS.md", "Shared"): "Shared",
        config_file_writer(
            project, ".cursor/rules/app/rule.mdc", "---\nalwaysApply: true\n---\nRule"
        ): "---\nalwaysApply: true\n---\nRule",
    }
    config_file_writer(project, ".cursor/rules/ignored.md", "Ignored")
    assert {
        path: [extension.canonical_config for extension in adapter.parse(path)]
        for path in adapter.locate_project_config(project)
    } == {
        config: [McpServerConfig(command="example")],
        **{
            path: [MemoryFileConfig(content=content, is_persistent_memory=False)]
            for path, content in instructions.items()
        },
    }


def test_project_precedes_user_when_both_define_same_server(
    adapter: CursorAdapter,
    home: Path,
    project: Path,
    config_file_writer: Callable[[Path, str, str], Path],
) -> None:
    user_config = config_file_writer(
        home, ".cursor/mcp.json", '{"mcpServers":{"same":{"command":"user"}}}'
    )
    project_config = config_file_writer(
        project, ".cursor/mcp.json", '{"mcpServers":{"same":{"command":"project"}}}'
    )
    layers = [
        layer
        for layer in adapter.precedence_chain(project).layers
        if isinstance(layer, ConsultedLayer) and layer.resolves
    ]
    assert [layer.scope for layer in layers] == [Scope.PROJECT, Scope.USER]
    assert [Path(layer.file_path) for layer in layers] == [project_config, user_config]
    assert layers[0].order_rank < layers[1].order_rank
    assert [
        (extension.name, extension.canonical_config)
        for layer in layers
        for extension in adapter.parse(Path(layer.file_path))
    ] == [
        ("same", McpServerConfig(command="project")),
        ("same", McpServerConfig(command="user")),
    ]
    assert adapter.walk_up_behavior(ExtensionType.MCP_SERVER).merge_semantics == (
        MergeSemantics.OVERRIDE
    )


def test_shared_consumption_when_agents_files_exist(
    adapter: CursorAdapter,
    home: Path,
    project: Path,
    config_file_writer: Callable[[Path, str, str], Path],
) -> None:
    native_instructions = config_file_writer(
        project, "AGENTS.md", "Project instructions"
    )
    shared_instructions = config_file_writer(
        project, ".agents/AGENTS.md", "Other instructions"
    )
    user_instructions = config_file_writer(
        home, ".agents/AGENTS.md", "User instructions"
    )
    project_skill = config_file_writer(
        project, ".agents/skills/project/SKILL.md", "---\nname: project\n---\nProject"
    )
    user_skill = config_file_writer(
        home, ".agents/skills/user/SKILL.md", "---\nname: user\n---\nUser"
    )
    layers = {
        Path(layer.file_path): layer
        for layer in adapter.precedence_chain(project).layers
    }
    for path in (native_instructions, project_skill, user_skill):
        assert isinstance(layers[path], ConsultedLayer)
        assert layers[path].resolves
    assert isinstance(layers[shared_instructions], UnconfirmedLayer)
    assert isinstance(layers[user_instructions], NotConsultedLayer)


def test_shared_instructions_resolve_once_when_linked_from_project_root(
    adapter: CursorAdapter,
    home: Path,
    project: Path,
    config_file_writer: Callable[[Path, str, str], Path],
) -> None:
    target = config_file_writer(project, ".agents/AGENTS.md", "Shared instructions")
    alias = project / "AGENTS.md"
    alias.symlink_to(target.relative_to(project))

    chain = DotAgentsAdapter(home=home).consumption_report(adapter, project)
    shared_layers = [
        layer for layer in chain.layers if Path(layer.file_path) in {alias, target}
    ]
    assert len(shared_layers) == 1
    layer = shared_layers[0]
    assert isinstance(layer, ConsultedLayer)
    assert layer.resolves
    assert layer.symlink_target == str(target)
