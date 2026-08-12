from typing import Protocol
from uuid import UUID

from agentctl.domain import Binding


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
