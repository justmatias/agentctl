from agentctl.adapters.common import (
    Serializer,
    serialize_mcp_server_toml,
    serialize_memory_file,
)
from agentctl.domain import (
    CanonicalConfig,
    McpServerConfig,
    MemoryFileConfig,
)

SERIALIZERS: dict[type[CanonicalConfig], Serializer] = {
    McpServerConfig: serialize_mcp_server_toml,
    MemoryFileConfig: serialize_memory_file,
}
