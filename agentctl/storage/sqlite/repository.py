from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Connection, RowMapping, Table, delete, select
from sqlalchemy.sql import Executable

from agentctl.utils import logger


class SqliteConnectionRepository:
    """Base for sqlite repositories sharing one long-lived connection.

    Holds the connection and the transactional-write helper, so that
    `SqliteRepository` and `SqlitePrecedenceChainRepository` — which don't
    share a CRUD contract (single `id` column vs. composite source/project
    key) and so can't inherit from one another — both get it without
    duplicating it.
    """

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def _write_in_transaction(
        self, statements: Sequence[Executable], *, message: str
    ) -> None:
        """Run `statements` as one atomic transaction, then log `message`.

        Uses commit-as-you-go rather than `connection.begin()`: this
        connection is held open for the repository's whole lifetime, so a
        prior read may have already autobegun a transaction, and `begin()`
        raises if called against one already in progress.
        """
        try:
            for statement in statements:
                self._connection.execute(statement)
        except Exception:
            self._connection.rollback()
            raise
        self._connection.commit()
        logger.info(message)


class SqliteRepository[T: BaseModel](SqliteConnectionRepository, ABC):
    """Shared CRUD for repositories keyed by a single `id` column."""

    _table: ClassVar[Table]
    _entity_name: ClassVar[str]

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
        self._write_in_transaction(
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
        self._write_in_transaction(
            [statement],
            message=f"{action} {self._entity_name} {item_id}{extra}",
        )

    @staticmethod
    @abstractmethod
    def _row_to_model(row: RowMapping) -> T: ...
