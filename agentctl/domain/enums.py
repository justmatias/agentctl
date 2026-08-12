from enum import Enum


class ExtensionType(str, Enum):
    """Managed config object types with a canonical shape in v1"""

    MCP_SERVER = "mcp_server"
    MEMORY_FILE = "memory_file"
    SKILL = "skill"


class Source(str, Enum):
    """A harness, or a non-runnable shared source such as .agents"""

    CLAUDE_CODE = "claude_code"
    CODEX_CLI = "codex_cli"
    OPENCODE = "opencode"
    CURSOR = "cursor"
    DOT_AGENTS = "dot_agents"


class Scope(str, Enum):
    """Where a binding lives on disk relative to precedence"""

    MANAGED = "managed"
    LOCAL = "local"
    PROJECT = "project"
    USER = "user"
    GLOBAL = "global"


class SyncState(str, Enum):
    """Whether a binding's on-disk content matches what the tool last wrote."""

    IN_SYNC = "in_sync"
    DRIFTED = "drifted"
    CONFLICT = "conflict"
    DIVERGENT = "divergent"
    UNMANAGED = "unmanaged"


class LayerStatus(str, Enum):
    """Whether an adapter has verified a source is consulted"""

    CONSULTED = "consulted"
    NOT_CONSULTED = "not_consulted"
    UNCONFIRMED = "unconfirmed"


class LayerOrigin(str, Enum):
    """Where a precedence layer's directory comes from"""

    REGISTERED_PROJECT = "registered_project"
    ANCESTOR_DIR = "ancestor_dir"
    GLOBAL = "global"


class ConflictResolution(str, Enum):
    """How a structured-config Conflict was resolved"""

    UNRESOLVED = "unresolved"
    SOURCE_CHOSEN = "source_chosen"
    KEEP_BOTH_INTENTIONALLY = "keep_both_intentionally"
