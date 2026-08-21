from agentctl.adapters.common import (
    Serializer,
    serialize_mcp_server_json,
    serialize_memory_file,
    serialize_skill,
)
from agentctl.domain import (
    CanonicalConfig,
    McpServerConfig,
    MemoryFileConfig,
    SkillConfig,
)

SERIALIZERS: dict[type[CanonicalConfig], Serializer] = {
    McpServerConfig: serialize_mcp_server_json,
    MemoryFileConfig: serialize_memory_file,
    SkillConfig: serialize_skill,
}
