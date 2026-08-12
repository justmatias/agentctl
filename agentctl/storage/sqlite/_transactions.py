from collections.abc import Sequence

from sqlalchemy import Connection
from sqlalchemy.sql import Executable

from agentctl.utils import logger


def write_in_transaction(
    connection: Connection, statements: Sequence[Executable], *, message: str
) -> None:
    """Run `statements` as one atomic transaction, then log `message`.

    Uses commit-as-you-go rather than `connection.begin()`: this connection
    is held open for the repository's whole lifetime, so a prior read may
    have already autobegun a transaction, and `begin()` raises if called
    against one already in progress.

    Shared by `SqliteRepository._write`/`delete` and
    `SqlitePrecedenceChainRepository`, whose delete-then-insert upsert
    can't reuse the single-statement base without this.
    """
    try:
        for statement in statements:
            connection.execute(statement)
    except Exception:
        connection.rollback()
        raise
    connection.commit()
    logger.info(message)
