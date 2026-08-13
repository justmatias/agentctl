import json
from collections.abc import Callable

import yaml

from agentctl.domain import (
    CanonicalConfig,
    Extension,
    McpServerConfig,
    MemoryFileConfig,
    SkillConfig,
)

Serializer = Callable[[Extension], str]


def serialize_mcp_server(extension: Extension) -> str:
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


SERIALIZERS: dict[type[CanonicalConfig], Serializer] = {
    McpServerConfig: serialize_mcp_server,
    MemoryFileConfig: serialize_memory_file,
    SkillConfig: serialize_skill,
}
