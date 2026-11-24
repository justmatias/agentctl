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
from .cursor import CursorAdapter
from .dot_agents import DotAgentsAdapter
from .fake import NullAdapter
from .opencode import OpenCodeAdapter
from .protocol import (
    AdapterCapabilities,
    MergeSemantics,
    ScopedConfigPath,
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
    "CursorAdapter",
    "DotAgentsAdapter",
    "MergeSemantics",
    "NullAdapter",
    "OpenCodeAdapter",
    "ScopedConfigPath",
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
