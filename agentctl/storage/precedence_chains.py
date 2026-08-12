from typing import Protocol
from uuid import UUID

from agentctl.domain import PrecedenceChain, Source


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
