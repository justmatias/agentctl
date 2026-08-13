import json
from collections.abc import Callable, Mapping

import yaml

from agentctl.domain import (
    CanonicalConfig,
    Extension,
    McpServerConfig,
    MemoryFileConfig,
    SkillConfig,
)

Serializer = Callable[[Extension], str]


def serialize_mcp_server_json(extension: Extension) -> str:
    """Render an MCP server as the `mcpServers` JSON object Claude Code and Cursor read."""
    config = extension.canonical_config
    assert isinstance(config, McpServerConfig)
    server = config.model_dump(exclude={"type"}, exclude_defaults=True)
    return json.dumps({"mcpServers": {extension.name: server}}, indent=2)


def serialize_memory_file(extension: Extension) -> str:
    config = extension.canonical_config
    assert isinstance(config, MemoryFileConfig)
    return config.content


def serialize_skill(extension: Extension) -> str:
    config = extension.canonical_config
    assert isinstance(config, SkillConfig)
    frontmatter = yaml.safe_dump(
        {"name": extension.name, "description": config.description},
        sort_keys=False,
    ).strip()
    return f"---\n{frontmatter}\n---\n\n{config.body}\n"


def dispatch_serializer(
    serializers: Mapping[type[CanonicalConfig], Serializer], extension: Extension
) -> str:
    """Render `extension` with the serializer a source declared for its config type."""
    serializer = serializers.get(type(extension.canonical_config))
    if not serializer:  # pragma: no cover
        raise TypeError(
            f"Unsupported canonical config type: {type(extension.canonical_config)!r}"
        )
    return serializer(extension)
