import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self

from .migrations import apply_migrations


class Database:
    """Owns a single SQLite connection, schema included.

    The DB holds orchestration metadata only (SPECS.md §9): it is disposable
    and rebuildable by rescan, never a source of truth for what a harness
    actually reads from disk.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        apply_migrations(self._connection)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
