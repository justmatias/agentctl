from pathlib import Path

import pytest

from agentctl.adapters import (
    AdapterRegistry,
    ClaudeCodeAdapter,
    CodexCliAdapter,
    CursorAdapter,
    DotAgentsAdapter,
    OpenCodeAdapter,
)
from agentctl.core import CoreService
from agentctl.storage import Database


@pytest.fixture
def registry(tmp_path: Path) -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register(OpenCodeAdapter(config_directory=tmp_path / "opencode"))
    registry.register(DotAgentsAdapter(home=tmp_path))
    registry.register(CursorAdapter(home=tmp_path))
    registry.register(
        CodexCliAdapter(
            codex_home=tmp_path / ".codex", system_config_directory=tmp_path / "system"
        )
    )
    registry.register(
        ClaudeCodeAdapter(
            home=tmp_path, managed_settings_path=tmp_path / "managed.json"
        )
    )
    return registry


@pytest.fixture
def installed_config(tmp_path: Path) -> dict[str, Path]:
    files = {
        ".claude.json": '{"mcpServers":{"alpha":{"command":"one"},"beta":{"command":"two"}}}',
        "system/config.toml": '[mcp_servers.local]\ncommand = "three"',
        ".cursor/mcp.json": '{"mcpServers":{"local":{"command":"four"}}}',
        ".agents/AGENTS.md": "Shared instructions",
        "opencode/opencode.json": '{"mcp":{"local":{"type":"local","command":["five"]}}}',
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return {name: tmp_path / name for name in files}


@pytest.fixture
def service(registry: AdapterRegistry, database: Database) -> CoreService:
    return CoreService(registry, database)
