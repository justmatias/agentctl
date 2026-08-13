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
