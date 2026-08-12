from abc import ABC, abstractmethod
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Connection, RowMapping, Table, delete, select
from sqlalchemy.sql import Executable

from ._transactions import write_in_transaction


class SqliteRepository[T: BaseModel](ABC):
    """Shared CRUD for repositories keyed by a single `id` column."""

    _table: ClassVar[Table]
    _entity_name: ClassVar[str]

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def get(self, item_id: UUID) -> T | None:
        row = (
            self._connection
            .execute(select(self._table).where(self._table.c.id == str(item_id)))
            .mappings()
            .fetchone()
        )
        return self._row_to_model(row) if row else None

    def list(self, *, order_by: str | None = None) -> list[T]:
        # `self._table.c[order_by]` raises KeyError for anything that isn't
        # an actual column name, so a caller-supplied value can't be used to
        # inject arbitrary SQL the way string interpolation could.
        query = select(self._table)
        if order_by:
            query = query.order_by(self._table.c[order_by])
        rows = self._connection.execute(query).mappings().fetchall()
        return [self._row_to_model(row) for row in rows]

    def delete(self, item_id: UUID) -> None:
        write_in_transaction(
            self._connection,
            [delete(self._table).where(self._table.c.id == str(item_id))],
            message=f"Deleted {self._entity_name} {item_id}",
        )

    def _write(
        self,
        statement: Executable,
        *,
        action: str,
        item_id: object,
        extra: str = "",
    ) -> None:
        write_in_transaction(
            self._connection,
            [statement],
            message=f"{action} {self._entity_name} {item_id}{extra}",
        )

    @staticmethod
    @abstractmethod
    def _row_to_model(row: RowMapping) -> T: ...
