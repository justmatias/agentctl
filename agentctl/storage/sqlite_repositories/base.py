import sqlite3
from abc import ABC, abstractmethod
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

from agentctl.utils import logger


class SqliteRepository[T: BaseModel](ABC):
    """Shared CRUD for repositories keyed by a single `id` column."""

    _table: ClassVar[str]
    _entity_name: ClassVar[str]
    _list_order_by: ClassVar[str | None] = None

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, item_id: UUID) -> T | None:
        row = self._connection.execute(
            f"SELECT * FROM {self._table} WHERE id = ?", (str(item_id),)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def list(self) -> list[T]:
        query = f"SELECT * FROM {self._table}"
        if self._list_order_by:
            query += f" ORDER BY {self._list_order_by}"
        rows = self._connection.execute(query).fetchall()
        return [self._row_to_model(row) for row in rows]

    def delete(self, item_id: UUID) -> None:
        self._write(
            f"DELETE FROM {self._table} WHERE id = ?",
            (str(item_id),),
            action="Deleted",
            item_id=item_id,
        )

    def _write(
        self,
        sql: str,
        params: tuple[object, ...],
        *,
        action: str,
        item_id: object,
        extra: str = "",
    ) -> None:
        with self._connection:
            self._connection.execute(sql, params)
        logger.info(f"{action} {self._entity_name} {item_id}{extra}")

    @staticmethod
    @abstractmethod
    def _row_to_model(row: sqlite3.Row) -> T: ...
