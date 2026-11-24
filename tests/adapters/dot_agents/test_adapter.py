from pathlib import Path

import pytest

from agentctl.adapters import ClaudeCodeAdapter, CodexCliAdapter, DotAgentsAdapter
from agentctl.domain import ConsultedLayer, LayerStatus, MemoryFileConfig


def test_locate_global_config_finds_shared_directory_and_memory_when_present(
    tmp_path: Path, global_shared_memory: Path, dot_agents_adapter: DotAgentsAdapter
) -> None:
    assert set(dot_agents_adapter.locate_global_config()) == {
        tmp_path / ".agents",
        global_shared_memory,
    }


def test_locate_project_config_finds_shared_and_root_files_when_present(
    empty_project_root: Path,
    project_shared_memory: Path,
    project_root_instruction_files: list[Path],
    dot_agents_adapter: DotAgentsAdapter,
) -> None:
    assert set(dot_agents_adapter.locate_project_config(empty_project_root)) == {
        empty_project_root / ".agents",
        project_shared_memory,
        *project_root_instruction_files,
    }


def test_parse_marks_content_as_persistent_memory_when_file_is_memory_md(
    project_shared_memory: Path, dot_agents_adapter: DotAgentsAdapter
) -> None:
    assert dot_agents_adapter.parse(project_shared_memory)[
        0
    ].canonical_config == MemoryFileConfig(content="notes", is_persistent_memory=True)


def test_consumption_report_keeps_native_winner_when_shared_memory_is_added(
    empty_project_root: Path,
    native_project_instructions: Path,
    dot_agents_adapter: DotAgentsAdapter,
    codex_cli_adapter: CodexCliAdapter,
) -> None:
    before = dot_agents_adapter.consumption_report(
        codex_cli_adapter, empty_project_root
    )
    shared = empty_project_root / ".agents" / "memory" / "MEMORY.md"
    shared.parent.mkdir(parents=True)
    shared.write_text("shared", encoding="utf-8")

    after = dot_agents_adapter.consumption_report(codex_cli_adapter, empty_project_root)

    winners = [layer for layer in after.layers if layer.resolves]
    assert winners == [layer for layer in before.layers if layer.resolves]
    assert winners[0].file_path == str(native_project_instructions)


@pytest.mark.usefixtures("native_project_instructions")
def test_consumption_report_appends_unranked_unconfirmed_layer_when_codex_ignores_shared_memory(
    empty_project_root: Path,
    project_shared_memory: Path,
    dot_agents_adapter: DotAgentsAdapter,
    codex_cli_adapter: CodexCliAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(codex_cli_adapter, empty_project_root)

    layer = chain.layers[-1]
    assert layer.file_path == str(project_shared_memory)
    assert layer.status == LayerStatus.UNCONFIRMED
    assert "order_rank" not in layer.model_dump()


def test_consumption_report_records_symlink_target_when_codex_reads_native_symlink(
    empty_project_root: Path,
    shared_instructions_target: Path,
    codex_native_symlink: Path,
    dot_agents_adapter: DotAgentsAdapter,
    codex_cli_adapter: CodexCliAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(codex_cli_adapter, empty_project_root)

    layer = next(
        layer for layer in chain.layers if layer.file_path == str(codex_native_symlink)
    )
    assert isinstance(layer, ConsultedLayer)
    assert layer.symlink_target == str(shared_instructions_target)


@pytest.mark.usefixtures("shared_instructions_target")
def test_consumption_report_resolves_codex_symlink_when_no_override_shadows_it(
    empty_project_root: Path,
    codex_native_symlink: Path,
    dot_agents_adapter: DotAgentsAdapter,
    codex_cli_adapter: CodexCliAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(codex_cli_adapter, empty_project_root)

    layer = next(
        layer for layer in chain.layers if layer.file_path == str(codex_native_symlink)
    )
    assert layer.resolves


@pytest.mark.usefixtures("_write_codex_override")
def test_consumption_report_records_symlink_target_when_codex_symlink_is_shadowed(
    empty_project_root: Path,
    shared_instructions_target: Path,
    codex_native_symlink: Path,
    dot_agents_adapter: DotAgentsAdapter,
    codex_cli_adapter: CodexCliAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(codex_cli_adapter, empty_project_root)

    layer = next(
        layer for layer in chain.layers if layer.file_path == str(codex_native_symlink)
    )
    assert isinstance(layer, ConsultedLayer)
    assert layer.symlink_target == str(shared_instructions_target)


@pytest.mark.usefixtures("shared_instructions_target", "codex_native_symlink")
def test_consumption_report_omits_shared_layer_when_codex_symlink_resolves(
    empty_project_root: Path,
    project_shared_instructions: Path,
    dot_agents_adapter: DotAgentsAdapter,
    codex_cli_adapter: CodexCliAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(codex_cli_adapter, empty_project_root)

    assert all(
        layer.file_path != str(project_shared_instructions) for layer in chain.layers
    )


@pytest.mark.usefixtures(
    "shared_instructions_target", "codex_native_symlink", "_write_codex_override"
)
def test_consumption_report_keeps_shared_layer_unconfirmed_when_codex_symlink_is_shadowed(
    empty_project_root: Path,
    project_shared_instructions: Path,
    dot_agents_adapter: DotAgentsAdapter,
    codex_cli_adapter: CodexCliAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(codex_cli_adapter, empty_project_root)

    assert [
        layer.status
        for layer in chain.layers
        if layer.file_path == str(project_shared_instructions)
    ] == [LayerStatus.UNCONFIRMED]


@pytest.mark.usefixtures("shared_instructions_target", "_write_codex_override")
def test_consumption_report_keeps_symlink_unresolved_when_codex_override_shadows_it(
    empty_project_root: Path,
    codex_native_symlink: Path,
    dot_agents_adapter: DotAgentsAdapter,
    codex_cli_adapter: CodexCliAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(codex_cli_adapter, empty_project_root)

    layer = next(
        layer for layer in chain.layers if layer.file_path == str(codex_native_symlink)
    )
    assert layer.status == LayerStatus.CONSULTED
    assert not layer.resolves


def test_consumption_report_marks_shared_instructions_not_consulted_when_harness_is_claude(
    global_shared_instructions: Path,
    dot_agents_adapter: DotAgentsAdapter,
    claude_code_adapter: ClaudeCodeAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(claude_code_adapter, None)

    layer = next(
        layer
        for layer in chain.layers
        if layer.file_path == str(global_shared_instructions)
    )
    assert layer.status == LayerStatus.NOT_CONSULTED
    assert not layer.resolves


def test_consumption_report_records_symlink_target_when_claude_reads_native_symlink(
    empty_project_root: Path,
    project_shared_instructions: Path,
    claude_native_symlink: Path,
    dot_agents_adapter: DotAgentsAdapter,
    claude_code_adapter: ClaudeCodeAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(
        claude_code_adapter, empty_project_root
    )

    layer = next(
        layer for layer in chain.layers if layer.file_path == str(claude_native_symlink)
    )
    assert isinstance(layer, ConsultedLayer)
    assert layer.resolves
    assert layer.symlink_target == str(project_shared_instructions)


@pytest.mark.usefixtures("claude_native_symlink")
def test_consumption_report_omits_shared_layer_when_claude_native_symlink_resolves(
    empty_project_root: Path,
    project_shared_instructions: Path,
    dot_agents_adapter: DotAgentsAdapter,
    claude_code_adapter: ClaudeCodeAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(
        claude_code_adapter, empty_project_root
    )

    assert all(
        layer.file_path != str(project_shared_instructions) for layer in chain.layers
    )


@pytest.mark.usefixtures("claude_native_symlink")
def test_consumption_report_keeps_root_memory_unconfirmed_when_it_links_to_shared_instructions(
    empty_project_root: Path,
    project_root_memory_symlink: Path,
    dot_agents_adapter: DotAgentsAdapter,
    claude_code_adapter: ClaudeCodeAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(
        claude_code_adapter, empty_project_root
    )

    layer = next(
        layer
        for layer in chain.layers
        if layer.file_path == str(project_root_memory_symlink)
    )
    assert layer.status == LayerStatus.UNCONFIRMED


def test_consumption_report_records_symlink_target_when_claude_auto_memory_links_to_shared_memory(
    empty_project_root: Path,
    global_shared_memory: Path,
    claude_auto_memory_symlink: Path,
    dot_agents_adapter: DotAgentsAdapter,
    claude_code_adapter: ClaudeCodeAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(
        claude_code_adapter, empty_project_root
    )

    layer = next(
        layer
        for layer in chain.layers
        if layer.file_path == str(claude_auto_memory_symlink)
    )
    assert isinstance(layer, ConsultedLayer)
    assert layer.resolves
    assert layer.symlink_target == str(global_shared_memory)


@pytest.mark.usefixtures("claude_auto_memory_symlink")
def test_consumption_report_omits_shared_memory_when_claude_auto_memory_links_to_it(
    empty_project_root: Path,
    global_shared_memory: Path,
    dot_agents_adapter: DotAgentsAdapter,
    claude_code_adapter: ClaudeCodeAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(
        claude_code_adapter, empty_project_root
    )

    assert all(layer.file_path != str(global_shared_memory) for layer in chain.layers)


@pytest.mark.usefixtures("_link_every_claude_instruction_path_to_shared")
def test_consumption_report_resolves_shared_target_once_when_several_claude_paths_link_to_it(
    empty_project_root: Path,
    project_shared_instructions: Path,
    dot_agents_adapter: DotAgentsAdapter,
    claude_code_adapter: ClaudeCodeAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(
        claude_code_adapter, empty_project_root
    )

    assert [
        layer.file_path
        for layer in chain.layers
        if isinstance(layer, ConsultedLayer)
        and layer.resolves
        and layer.symlink_target == str(project_shared_instructions)
    ] == [str(empty_project_root / "CLAUDE.local.md")]


@pytest.mark.usefixtures(
    "_link_shared_instructions_to_root_agents_md",
    "_enable_claude_agents_md_loading",
)
def test_consumption_report_resolves_file_once_when_claude_loads_it_through_symlink_and_directly(
    empty_project_root: Path,
    native_project_instructions: Path,
    dot_agents_adapter: DotAgentsAdapter,
    claude_code_adapter: ClaudeCodeAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(
        claude_code_adapter, empty_project_root
    )

    assert [
        layer.file_path
        for layer in chain.layers
        if layer.resolves
        and Path(layer.file_path).resolve() == native_project_instructions
    ] == [str(empty_project_root / "CLAUDE.md")]


@pytest.mark.usefixtures("project_shared_memory")
def test_consumption_report_leaves_symlink_target_unset_when_claude_md_links_outside_shared_files(
    empty_project_root: Path,
    claude_md_symlink_to_root_agents_md: Path,
    dot_agents_adapter: DotAgentsAdapter,
    claude_code_adapter: ClaudeCodeAdapter,
) -> None:
    chain = dot_agents_adapter.consumption_report(
        claude_code_adapter, empty_project_root
    )

    layer = next(
        layer
        for layer in chain.layers
        if layer.file_path == str(claude_md_symlink_to_root_agents_md)
    )
    assert isinstance(layer, ConsultedLayer)
    assert layer.symlink_target is None
