from typing import Protocol
from uuid import UUID

from agentctl.domain import (
    Binding,
    Conflict,
    Extension,
    PrecedenceChain,
    Project,
    Source,
)


class Repository[T](Protocol):
    """Shared shape for repositories keyed by a single `id` column."""

    def create(self, item: T) -> None: ...
    def get(self, item_id: UUID) -> T | None: ...
    def list(self) -> list[T]: ...
    def update(self, item: T) -> None: ...
    def delete(self, item_id: UUID) -> None: ...


class ExtensionRepository(Repository[Extension], Protocol):
    pass


class BindingRepository(Repository[Binding], Protocol):
    def list_for_extension(self, extension_id: UUID) -> list[Binding]: ...


class ConflictRepository(Repository[Conflict], Protocol):
    pass


class ProjectRepository(Repository[Project], Protocol):
    pass


class PrecedenceChainRepository(Protocol):
    """Keyed by (source, project_id), not by an id — PrecedenceChain has none.

    A cache of the last-computed chain (SPECS.md §9): callers must still
    treat a scan as the source of truth for display and never present a
    cached row here as current.
    """

    def upsert(self, chain: PrecedenceChain) -> None: ...
    def get(
        self, source: Source, project_id: UUID | None
    ) -> PrecedenceChain | None: ...
    def list(self) -> list[PrecedenceChain]: ...
    def delete(self, source: Source, project_id: UUID | None) -> None: ...
