from pathlib import Path

import pytest

from agentctl.adapters import ClaudeCodeAdapter, CodexCliAdapter, DotAgentsAdapter
from tests.adapters.claude_code.helpers import agents_md_plugin_settings
from tests.adapters.dot_agents.helpers import write_file


@pytest.fixture
def dot_agents_adapter(tmp_path: Path) -> DotAgentsAdapter:
    return DotAgentsAdapter(home=tmp_path)


@pytest.fixture
def codex_cli_adapter(tmp_path: Path) -> CodexCliAdapter:
    return CodexCliAdapter(
        codex_home=tmp_path / ".codex", system_config_directory=tmp_path / "system"
    )


@pytest.fixture
def claude_code_adapter(tmp_path: Path) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(
        home=tmp_path, managed_settings_path=tmp_path / "settings.json"
    )


@pytest.fixture
def global_shared_instructions(tmp_path: Path) -> Path:
    return write_file(tmp_path / ".agents" / "AGENTS.md", "shared")


@pytest.fixture
def global_shared_memory(tmp_path: Path) -> Path:
    return write_file(tmp_path / ".agents" / "memory" / "MEMORY.md", "notes")


@pytest.fixture
def project_shared_instructions(empty_project_root: Path) -> Path:
    return write_file(empty_project_root / ".agents" / "AGENTS.md", "shared")


@pytest.fixture
def project_shared_memory(empty_project_root: Path) -> Path:
    return write_file(
        empty_project_root / ".agents" / "memory" / "MEMORY.md", "notes"
    )


@pytest.fixture
def project_root_instruction_files(empty_project_root: Path) -> list[Path]:
    return [
        write_file(empty_project_root / filename, "notes")
        for filename in ("AGENTS.md", "MEMORY.md")
    ]


@pytest.fixture
def native_project_instructions(empty_project_root: Path) -> Path:
    return write_file(empty_project_root / "AGENTS.md", "native")


@pytest.fixture(params=["local", "external"])
def shared_instructions_target(
    request: pytest.FixtureRequest, project_shared_instructions: Path
) -> Path:
    """The file `.agents/AGENTS.md` resolves to, inside or outside the project."""
    if request.param == "local":
        return project_shared_instructions
    project = project_shared_instructions.parent.parent
    target = project_shared_instructions.rename(project.parent / "dotfiles.md")
    project_shared_instructions.symlink_to(target)
    return target


@pytest.fixture
def codex_native_symlink(
    empty_project_root: Path, project_shared_instructions: Path
) -> Path:
    path = empty_project_root / "AGENTS.md"
    path.symlink_to(project_shared_instructions.relative_to(empty_project_root))
    return path


@pytest.fixture
def _write_codex_override(empty_project_root: Path) -> None:
    write_file(empty_project_root / "AGENTS.override.md", "override")


@pytest.fixture(params=["CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"])
def claude_native_symlink(
    request: pytest.FixtureRequest,
    empty_project_root: Path,
    project_shared_instructions: Path,
) -> Path:
    path: Path = empty_project_root / request.param
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(project_shared_instructions)
    return path


@pytest.fixture
def project_root_memory_symlink(
    empty_project_root: Path, project_shared_instructions: Path
) -> Path:
    path = empty_project_root / "MEMORY.md"
    path.symlink_to(project_shared_instructions)
    return path


@pytest.fixture
def claude_auto_memory_symlink(
    empty_project_root: Path,
    global_shared_memory: Path,
    claude_code_adapter: ClaudeCodeAdapter,
) -> Path:
    path = claude_code_adapter.auto_memory_path(empty_project_root)
    path.parent.mkdir(parents=True)
    path.symlink_to(global_shared_memory)
    return path


@pytest.fixture
def _link_every_claude_instruction_path_to_shared(
    empty_project_root: Path, project_shared_instructions: Path
) -> None:
    for filename in ("CLAUDE.local.md", ".claude/CLAUDE.md", "CLAUDE.md"):
        path = empty_project_root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(project_shared_instructions)


@pytest.fixture
def _link_claude_and_shared_instructions_to_root_agents_md(
    empty_project_root: Path, native_project_instructions: Path
) -> None:
    """CLAUDE.md and `.agents/AGENTS.md` both alias the root AGENTS.md."""
    for path in (
        empty_project_root / "CLAUDE.md",
        empty_project_root / ".agents" / "AGENTS.md",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(native_project_instructions)


@pytest.fixture
def _enable_claude_agents_md_loading(claude_code_adapter: ClaudeCodeAdapter) -> None:
    write_file(claude_code_adapter.user_settings_path, agents_md_plugin_settings())
