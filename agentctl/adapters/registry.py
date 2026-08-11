"""Adapter registry: register, look up, and enumerate SourceAdapters (ROADMAP.md PR 0.4)."""

from agentctl.domain import Source
from agentctl.utils import logger

from .protocol import SourceAdapter


class AdapterRegistry:
    """Discovery surface over whichever adapters have been registered.

    Adding a harness means registering a new SourceAdapter here — nothing
    else in the tool references a harness by name (SPECS §9).
    """

    def __init__(self) -> None:
        self._adapters: dict[Source, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        if not isinstance(adapter, SourceAdapter):
            raise TypeError(
                f"{adapter!r} does not implement the SourceAdapter protocol"
            )
        if adapter.source != adapter.capabilities.source:
            raise ValueError(
                f"adapter.source ({adapter.source!r}) does not match "
                f"adapter.capabilities.source ({adapter.capabilities.source!r})"
            )
        if adapter.source in self._adapters:
            logger.warning(f"Replacing already-registered adapter for {adapter.source}")
        else:
            logger.info(f"Registered adapter for {adapter.source}")
        self._adapters[adapter.source] = adapter

    def unregister(self, source: Source) -> None:
        if self._adapters.pop(source, None) is not None:
            logger.info(f"Unregistered adapter for {source}")

    def get(self, source: Source) -> SourceAdapter | None:
        return self._adapters.get(source)

    def list(self) -> list[SourceAdapter]:
        return list(self._adapters.values())
