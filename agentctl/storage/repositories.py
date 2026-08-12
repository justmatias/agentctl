from typing import Protocol
from uuid import UUID

from agentctl.domain import Binding, PrecedenceChain, Source


class Repository[T](Protocol):
    """Shared shape for repositories keyed by a single `id` column.

    Structural, not nominal: `Extension`/`Conflict`/`Project` repositories use
    this shape directly as `Repository[Extension]` etc. rather than declaring
    empty named subclasses — a Protocol needs no inheritance to be satisfied.
    """

    def create(self, item: T) -> None: ...
    def get(self, item_id: UUID) -> T | None: ...
    def list(self) -> list[T]: ...
    def update(self, item: T) -> None: ...
    def delete(self, item_id: UUID) -> None: ...


class BindingRepository(Repository[Binding], Protocol):
    """`Repository[Binding]` plus the extension-scoped lookup bindings need."""

    def list_for_extension(self, extension_id: UUID) -> list[Binding]: ...


class PrecedenceChainStore(Protocol):
    """Keyed by (source, project_id), not by an id — PrecedenceChain has none.

    Deliberately not a `Repository[T]`: the key shape and `upsert` (no
    separate create/update) differ from the rest of the storage layer. A
    cache of the last-computed chain (SPECS.md §9): callers must still treat
    a scan as the source of truth for display and never present a cached row
    here as current.
    """

    def upsert(self, chain: PrecedenceChain) -> None: ...
    def get(
        self, source: Source, project_id: UUID | None
    ) -> PrecedenceChain | None: ...
    def list(self) -> list[PrecedenceChain]: ...
    def delete(self, source: Source, project_id: UUID | None) -> None: ...
