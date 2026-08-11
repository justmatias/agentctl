"""Phase-0 domain model: enums, canonical config shapes, and core records."""

from .canonical_configs import (
    CanonicalConfig,
    McpServerConfig,
    MemoryFileConfig,
    SkillConfig,
)
from .enums import (
    ConflictResolution,
    ExtensionType,
    LayerOrigin,
    LayerStatus,
    Scope,
    Source,
    SyncState,
)
from .models import (
    Binding,
    Conflict,
    Extension,
    PrecedenceChain,
    PrecedenceLayer,
    Project,
)

__all__ = [
    "Binding",
    "CanonicalConfig",
    "Conflict",
    "ConflictResolution",
    "Extension",
    "ExtensionType",
    "LayerOrigin",
    "LayerStatus",
    "McpServerConfig",
    "MemoryFileConfig",
    "PrecedenceChain",
    "PrecedenceLayer",
    "Project",
    "Scope",
    "SkillConfig",
    "Source",
    "SyncState",
]
