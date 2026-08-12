from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Column, ColumnElement, delete, insert, update
from sqlalchemy.sql import Executable
from sqlmodel import Session, SQLModel, select

from agentctl.storage.repositories import FilterValue
from agentctl.utils import logger


class SqliteRepository[DomainT: BaseModel, RowT: SQLModel]:
    """Generic CRUD over a single SQLModel row type.

    Keyed by `_natural_key` (a single `id` column by default; a composite
    key such as `(source, project_id)` for `PrecedenceChain`, which has no
    `id` of its own).
    """

    _domain_model: type[DomainT]
    _row_model: type[RowT]
    _natural_key: ClassVar[tuple[str, ...]] = ("id",)
    _default_order_by: ClassVar[str | None] = None

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def _entity_name(self) -> str:
        return self._domain_model.__name__.lower()

    def create(self, item: DomainT) -> None:
        self._write_in_transaction(
            [insert(self._row_model).values(**self._to_row(item))],
            message=f"Created {self._entity_name} {self._identity(item)}",
        )

    def get(self, item_id: UUID) -> DomainT | None:
        return self.find_one(id=item_id)

    def find(self, **filters: FilterValue) -> list[DomainT]:
        query = select(self._row_model)
        for name, value in filters.items():
            query = query.where(self._filter_clause(name, value))
        return [self._to_domain(row) for row in self._session.exec(query).all()]

    def find_one(self, **filters: FilterValue) -> DomainT | None:
        results = self.find(**filters)
        return results[0] if results else None

    def list(self, *, order_by: str | None = None) -> list[DomainT]:
        query = select(self._row_model)
        column_name = order_by or self._default_order_by
        if column_name:
            query = query.order_by(self._column(column_name))
        return [self._to_domain(row) for row in self._session.exec(query).all()]

    def update(self, item: DomainT) -> None:
        statement = update(self._row_model)
        for key in self._natural_key:
            statement = statement.where(
                self._column(key) == self._encode(getattr(item, key))
            )
        self._write_in_transaction(
            [statement.values(**self._to_row(item))],
            message=f"Updated {self._entity_name} {self._identity(item)}",
        )

    def upsert(self, item: DomainT) -> None:
        self._write_in_transaction(
            [
                self._natural_key_delete(item),
                insert(self._row_model).values(**self._to_row(item)),
            ],
            message=f"Upserted {self._entity_name} {self._identity(item)}",
        )

    def delete(self, item_id: UUID) -> None:
        self.delete_where(id=item_id)

    def delete_where(self, **filters: FilterValue) -> None:
        statement = delete(self._row_model)
        for name, value in filters.items():
            statement = statement.where(self._filter_clause(name, value))
        self._write_in_transaction(
            [statement],
            message=f"Deleted {self._entity_name} ({filters})",
        )

    def _natural_key_delete(self, item: DomainT) -> Executable:
        statement = delete(self._row_model)
        for key in self._natural_key:
            statement = statement.where(
                self._column(key) == self._encode(getattr(item, key))
            )
        return statement

    def _identity(self, item: DomainT) -> str:
        values = [str(getattr(item, key)) for key in self._natural_key]
        if len(values) == 1:
            return values[0]
        pairs = zip(self._natural_key, values, strict=True)
        return ", ".join(f"{key}={value}" for key, value in pairs)

    def _to_row(self, item: DomainT) -> dict[str, object]:
        return self._row_model(**item.model_dump(mode="json")).model_dump()

    def _to_domain(self, row: RowT) -> DomainT:
        return self._domain_model.model_validate(row.model_dump())

    def _column(self, name: str) -> Column[Any]:
        # `self._row_model.__table__.c[name]` raises KeyError for anything
        # that isn't a real column name, so a caller-supplied value (via
        # `order_by` or any filter kwarg) can't be used to inject arbitrary
        # SQL the way string interpolation could.
        table = self._row_model.__table__  # type: ignore[attr-defined]
        return cast(Column[Any], table.c[name])

    def _filter_clause(self, name: str, value: FilterValue) -> ColumnElement[bool]:
        column = self._column(name)
        encoded = self._encode(value)
        return column.is_(None) if encoded is None else column == encoded

    @staticmethod
    def _encode(value: FilterValue) -> object:
        # `Enum.value` is typed `Any` in typeshed for the base `Enum` class
        # (subclasses narrow it), so this can't return a tighter alias
        # without mypy flagging that branch under `warn_return_any`.
        if isinstance(value, UUID | Path):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _write_in_transaction(
        self, statements: Sequence[Executable], *, message: str
    ) -> None:
        """Run `statements` as one atomic transaction, then log `message`.

        Uses commit-as-you-go rather than `session.begin()`: this session is
        held open for the repository's whole lifetime, so a prior read may
        have already autobegun a transaction, and `begin()` raises if called
        against one already in progress.
        """
        try:
            for statement in statements:
                self._session.execute(statement)
        except Exception:
            self._session.rollback()
            raise
        self._session.commit()
        logger.info(message)
