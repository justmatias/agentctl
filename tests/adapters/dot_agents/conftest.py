from pathlib import Path

import pytest

from agentctl.adapters import ClaudeCodeAdapter, CodexCliAdapter, DotAgentsAdapter


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
def project_shared_instructions(empty_project_root: Path) -> Path:
    path = empty_project_root / ".agents" / "AGENTS.md"
    path.parent.mkdir()
    path.write_text("shared", encoding="utf-8")
    return path
