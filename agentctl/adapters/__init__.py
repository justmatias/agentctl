"""Source adapter protocol and registry (ROADMAP.md PR 0.4)."""

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
    "MergeSemantics",
    "SourceAdapter",
    "WalkUpBehavior",
    "WalkUpStop",
    "WorkflowTargetForm",
]
