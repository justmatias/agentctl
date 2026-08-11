"""Adapter registry: register, look up, and enumerate SourceAdapters (ROADMAP.md PR 0.4)."""

from agentctl.domain import Source

from .protocol import SourceAdapter


class AdapterRegistry:
    """Discovery surface over whichever adapters have been registered.

    Adding a harness means registering a new SourceAdapter here — nothing
    else in the tool references a harness by name (SPECS §9).
    """

    def __init__(self) -> None:
        self._adapters: dict[Source, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        self._adapters[adapter.source] = adapter

    def unregister(self, source: Source) -> None:
        self._adapters.pop(source, None)

    def get(self, source: Source) -> SourceAdapter | None:
        return self._adapters.get(source)

    def list(self) -> list[SourceAdapter]:
        return list(self._adapters.values())
