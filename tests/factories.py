"""Shared domain-model factories for building fixtures across test modules."""

from uuid import UUID

from agentctl.domain import (
    Binding,
    Extension,
    ExtensionType,
    McpServerConfig,
    Scope,
    Source,
)


def make_extension(**overrides: object) -> Extension:
    defaults: dict[str, object] = {
        "type": ExtensionType.MCP_SERVER,
        "name": "github",
        "canonical_config": McpServerConfig(command="npx", args=["-y", "github-mcp"]),
    }
    defaults.update(overrides)
    return Extension(**defaults)


def make_binding(extension_id: UUID, **overrides: object) -> Binding:
    defaults: dict[str, object] = {
        "extension_id": extension_id,
        "harness": Source.CLAUDE_CODE,
        "scope": Scope.PROJECT,
        "file_path": ".claude/settings.json",
    }
    defaults.update(overrides)
    return Binding(**defaults)
