from pathlib import Path
from types import TracebackType
from typing import Self

from sqlalchemy import Connection, Engine, create_engine, event
from sqlmodel import Session

from .migrations import apply_migrations


def _configure_connection(dbapi_connection: object, _connection_record: object) -> None:
    # pysqlite auto-commits DDL outside of any transaction SQLAlchemy tracks,
    # which is what made the old executescript()-based migrations
    # non-atomic. Disabling its own transaction handling (isolation_level =
    # None) and driving BEGIN ourselves (see the "begin" event listener
    # below) is the documented SQLAlchemy recipe for genuinely
    # transactional SQLite DDL:
    # https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
    dbapi_connection.isolation_level = None  # type: ignore[attr-defined]
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


def create_sqlite_engine(path: str | Path = ":memory:") -> Engine:
    """A SQLite `Engine` with foreign keys enforced and DDL genuinely
    transactional, so a failed multi-statement migration rolls back in
    full rather than leaving earlier CREATE TABLE statements committed.
    """
    engine = create_engine(f"sqlite:///{path}")
    event.listen(engine, "connect", _configure_connection)
    event.listen(
        engine, "begin", lambda connection: connection.exec_driver_sql("BEGIN")
    )
    return engine


class Database:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._engine: Engine = create_sqlite_engine(path)
        self._connection: Connection = self._engine.connect()
        apply_migrations(self._connection)
        # `control_fully` is load-bearing: without it, a read issued through
        # `self._connection` autobegins a transaction the Session would then
        # refuse to commit, and repository writes would silently not persist.
        self._session = Session(
            bind=self._connection,
            expire_on_commit=False,
            join_transaction_mode="control_fully",
        )

    @property
    def connection(self) -> Connection:
        return self._connection

    @property
    def session(self) -> Session:
        return self._session

    def close(self) -> None:
        self._session.close()
        self._connection.close()
        self._engine.dispose()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
