from enum import StrEnum


class ExtensionType(StrEnum):
    """Managed config object types with a canonical shape in v1"""

    MCP_SERVER = "mcp_server"
    MEMORY_FILE = "memory_file"
    SKILL = "skill"


class Source(StrEnum):
    """A harness, or a non-runnable shared source such as .agents"""

    CLAUDE_CODE = "claude_code"
    CODEX_CLI = "codex_cli"
    OPENCODE = "opencode"
    CURSOR = "cursor"
    DOT_AGENTS = "dot_agents"


class Scope(StrEnum):
    """Where a binding lives on disk relative to precedence"""

    MANAGED = "managed"
    LOCAL = "local"
    PROJECT = "project"
    USER = "user"
    GLOBAL = "global"


class SyncState(StrEnum):
    """Whether a binding's on-disk content matches what the tool last wrote."""

    UNADOPTED = "unadopted"
    IN_SYNC = "in_sync"
    DRIFTED = "drifted"
    CONFLICT = "conflict"
    DIVERGENT = "divergent"
    UNMANAGED = "unmanaged"


class LayerStatus(StrEnum):
    """Whether an adapter has verified a source is consulted"""

    CONSULTED = "consulted"
    NOT_CONSULTED = "not_consulted"
    UNCONFIRMED = "unconfirmed"


class LayerOrigin(StrEnum):
    """Where a precedence layer's directory comes from"""

    REGISTERED_PROJECT = "registered_project"
    ANCESTOR_DIR = "ancestor_dir"
    GLOBAL = "global"


class ConflictResolution(StrEnum):
    """How a structured-config Conflict was resolved"""

    UNRESOLVED = "unresolved"
    SOURCE_CHOSEN = "source_chosen"
    KEEP_BOTH_INTENTIONALLY = "keep_both_intentionally"
