from pathlib import Path

import pytest

from agentctl.adapters import ClaudeCodeAdapter, CodexCliAdapter, DotAgentsAdapter
from agentctl.domain import ConsultedLayer, LayerStatus, MemoryFileConfig


def test_shared_inventory_is_available_without_a_harness(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    global_memory = home / ".agents" / "memory" / "MEMORY.md"
    project_memory = project / ".agents" / "memory" / "MEMORY.md"
    for path in (
        global_memory,
        project_memory,
        project / "AGENTS.md",
        project / "MEMORY.md",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("notes", encoding="utf-8")

    adapter = DotAgentsAdapter(home=home)

    assert set(adapter.locate_global_config()) == {home / ".agents", global_memory}
    assert set(adapter.locate_project_config(project)) == {
        project / ".agents",
        project_memory,
        project / "AGENTS.md",
        project / "MEMORY.md",
    }
    assert adapter.parse(project_memory)[0].canonical_config == MemoryFileConfig(
        content="notes", is_persistent_memory=True
    )


def test_winner_stays_the_same_when_shared_support_is_unconfirmed(
    empty_project_root: Path,
    dot_agents_adapter: DotAgentsAdapter,
    codex_cli_adapter: CodexCliAdapter,
) -> None:
    project = empty_project_root
    shared = project / ".agents" / "memory" / "MEMORY.md"
    shared.parent.mkdir(parents=True)
    native = project / "AGENTS.md"
    native.write_text("native", encoding="utf-8")
    before = dot_agents_adapter.consumption_report(codex_cli_adapter, project)
    shared.write_text("shared", encoding="utf-8")
    after = dot_agents_adapter.consumption_report(codex_cli_adapter, project)

    assert [layer for layer in before.layers if layer.resolves] == [
        layer for layer in after.layers if layer.resolves
    ]
    assert next(layer for layer in after.layers if layer.resolves).file_path == str(
        native
    )
    layer = after.layers[-1]
    assert layer.file_path == str(shared)
    assert layer.status == LayerStatus.UNCONFIRMED
    assert "order_rank" not in layer.model_dump()


@pytest.mark.parametrize("external_target", [False, True], ids=["local", "external"])
@pytest.mark.parametrize("shadowed", [False, True], ids=["active", "shadowed"])
def test_report_uses_codex_symlink_only_when_it_resolves(
    tmp_path: Path,
    shadowed: bool,
    external_target: bool,
    empty_project_root: Path,
    project_shared_instructions: Path,
    dot_agents_adapter: DotAgentsAdapter,
    codex_cli_adapter: CodexCliAdapter,
) -> None:
    project = empty_project_root
    shared = project_shared_instructions
    target = shared
    if external_target:
        target = shared.rename(tmp_path / "dotfiles.md")
        shared.symlink_to(target)
    native = project / "AGENTS.md"
    native.symlink_to(Path(".agents/AGENTS.md"))
    if shadowed:
        (project / "AGENTS.override.md").write_text("override", encoding="utf-8")

    chain = dot_agents_adapter.consumption_report(codex_cli_adapter, project)

    shared_layers = [layer for layer in chain.layers if layer.file_path == str(shared)]
    assert [layer.status for layer in shared_layers] == (
        [LayerStatus.UNCONFIRMED] if shadowed else []
    )
    layer = next(layer for layer in chain.layers if layer.file_path == str(native))
    assert layer.status == LayerStatus.CONSULTED
    assert layer.resolves is not shadowed
    assert isinstance(layer, ConsultedLayer)
    assert layer.symlink_target == str(target)


def test_report_uses_documented_direct_exclusion_for_claude(
    tmp_path: Path,
    dot_agents_adapter: DotAgentsAdapter,
    claude_code_adapter: ClaudeCodeAdapter,
) -> None:
    shared = tmp_path / ".agents" / "AGENTS.md"
    shared.parent.mkdir()
    shared.write_text("shared", encoding="utf-8")

    chain = dot_agents_adapter.consumption_report(claude_code_adapter, None)

    layer = next(layer for layer in chain.layers if layer.file_path == str(shared))
    assert layer.status == LayerStatus.NOT_CONSULTED
    assert not layer.resolves


@pytest.mark.parametrize(
    "filename", ["CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"]
)
def test_report_records_shared_instructions_when_claude_reads_a_native_symlink(
    filename: str,
    empty_project_root: Path,
    project_shared_instructions: Path,
    dot_agents_adapter: DotAgentsAdapter,
    claude_code_adapter: ClaudeCodeAdapter,
) -> None:
    project = empty_project_root
    shared = project_shared_instructions
    native = project / filename
    native.parent.mkdir(parents=True, exist_ok=True)
    native.symlink_to(shared)
    root_memory = project / "MEMORY.md"
    root_memory.symlink_to(shared)

    chain = dot_agents_adapter.consumption_report(claude_code_adapter, project)

    assert all(layer.file_path != str(shared) for layer in chain.layers)
    assert (
        next(
            layer for layer in chain.layers if layer.file_path == str(root_memory)
        ).status
        == LayerStatus.UNCONFIRMED
    )
    layer = next(layer for layer in chain.layers if layer.file_path == str(native))
    assert isinstance(layer, ConsultedLayer)
    assert layer.resolves
    assert layer.symlink_target == str(shared)
