from sqlalchemy import RowMapping, insert, update

from agentctl.domain import Conflict

from ..schema import conflicts
from .repository import SqliteRepository


class SqliteConflictRepository(SqliteRepository[Conflict]):
    _table = conflicts
    _entity_name = "conflict"

    def create(self, conflict: Conflict) -> None:
        self._write(
            insert(conflicts).values(id=str(conflict.id), **self._values(conflict)),
            action="Created",
            item_id=conflict.id,
            extra=f" for extension {conflict.extension_id}",
        )

    def update(self, conflict: Conflict) -> None:
        self._write(
            update(conflicts)
            .where(conflicts.c.id == str(conflict.id))
            .values(**self._values(conflict)),
            action="Updated",
            item_id=conflict.id,
        )

    @staticmethod
    def _values(conflict: Conflict) -> dict[str, object]:
        return {
            "extension_id": str(conflict.extension_id),
            "binding_ids": [str(binding_id) for binding_id in conflict.binding_ids],
            "resolved_binding_id": (
                str(conflict.resolved_binding_id)
                if conflict.resolved_binding_id
                else None
            ),
            "resolution": conflict.resolution.value,
        }

    @staticmethod
    def _row_to_model(row: RowMapping) -> Conflict:
        return Conflict.model_validate(dict(row))
