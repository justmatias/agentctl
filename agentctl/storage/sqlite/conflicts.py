import json
import sqlite3

from agentctl.domain import Conflict

from .repository import SqliteRepository


class SqliteConflictRepository(SqliteRepository[Conflict]):
    _table = "conflicts"
    _entity_name = "conflict"

    def create(self, conflict: Conflict) -> None:
        self._write(
            """
            INSERT INTO conflicts
                (id, extension_id, binding_ids, resolved_binding_id, resolution)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(conflict.id),
                str(conflict.extension_id),
                json.dumps([str(bid) for bid in conflict.binding_ids]),
                str(conflict.resolved_binding_id)
                if conflict.resolved_binding_id
                else None,
                conflict.resolution.value,
            ),
            action="Created",
            item_id=conflict.id,
            extra=f" for extension {conflict.extension_id}",
        )

    def update(self, conflict: Conflict) -> None:
        self._write(
            """
            UPDATE conflicts
            SET extension_id = ?, binding_ids = ?, resolved_binding_id = ?, resolution = ?
            WHERE id = ?
            """,
            (
                str(conflict.extension_id),
                json.dumps([str(bid) for bid in conflict.binding_ids]),
                str(conflict.resolved_binding_id)
                if conflict.resolved_binding_id
                else None,
                conflict.resolution.value,
                str(conflict.id),
            ),
            action="Updated",
            item_id=conflict.id,
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Conflict:
        return Conflict.model_validate({
            **dict(row),
            "binding_ids": json.loads(row["binding_ids"]),
        })
