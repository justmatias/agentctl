# pylint: disable=duplicate-code
from .claude_code import ClaudeCodeAdapter
from .codex_cli import CodexCliAdapter
from .common import (
    Serializer,
    consulted_file_layer,
    dispatch_serializer,
    parse_mcp_servers_json,
    parse_mcp_servers_toml,
    parse_memory_file,
    parse_skill,
    platform_specific_path,
    serialize_mcp_server_json,
    serialize_mcp_server_toml,
    serialize_memory_file,
    serialize_skill,
)
from .fake import NullAdapter
from .protocol import (
    AdapterCapabilities,
    MergeSemantics,
    SourceAdapter,
    WalkUpBehavior,
    WalkUpStop,
    WorkflowTargetForm,
)
from .registry import AdapterRegistry

__all__ = [
    "AdapterCapabilities",
    "AdapterRegistry",
    "ClaudeCodeAdapter",
    "CodexCliAdapter",
    "MergeSemantics",
    "NullAdapter",
    "Serializer",
    "SourceAdapter",
    "WalkUpBehavior",
    "WalkUpStop",
    "WorkflowTargetForm",
    "consulted_file_layer",
    "dispatch_serializer",
    "parse_mcp_servers_json",
    "parse_mcp_servers_toml",
    "parse_memory_file",
    "parse_skill",
    "platform_specific_path",
    "serialize_mcp_server_json",
    "serialize_mcp_server_toml",
    "serialize_memory_file",
    "serialize_skill",
]
