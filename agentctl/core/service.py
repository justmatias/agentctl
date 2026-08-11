"""Framework-agnostic core service: orchestrates adapters + storage (SPECS.md §9).

This is the skeleton Phase 1 plugs into. Detection logic — inventory
(PR 1.6), drift (PR 1.8), conflicts (PR 1.9) — lands once real adapters
exist; this PR only wires the orchestration seam together so those PRs
have somewhere to attach.
"""

from dataclasses import dataclass

from agentctl.adapters import AdapterRegistry
from agentctl.domain import Source
from agentctl.storage import Database


@dataclass
class CoreService:
    """Owns adapter discovery and the storage connection for one process."""

    registry: AdapterRegistry
    database: Database

    def registered_sources(self) -> list[Source]:
        """Every source currently registered, in registration order."""
        return [adapter.source for adapter in self.registry.list()]
