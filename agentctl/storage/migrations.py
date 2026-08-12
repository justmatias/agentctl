from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError

from agentctl.utils import logger

from .schema import metadata, schema_migrations


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    apply: Callable[[Connection], None]


def _create_initial_schema(connection: Connection) -> None:
    metadata.create_all(connection, checkfirst=True)


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="Orchestration metadata tables",
        apply=_create_initial_schema,
    ),
)


def apply_migrations(
    connection: Connection, migrations: tuple[Migration, ...] = MIGRATIONS
) -> None:
    """Apply every migration not yet recorded in `schema_migrations`, in order.

    Each migration commits as one unit (commit-as-you-go, since this
    connection stays open for the caller's lifetime — see
    `SqliteConnectionRepository._write_in_transaction`), so a failure
    partway through rolls back everything the migration already did —
    SQLite DDL is transactional — rather than leaving earlier statements
    committed.
    """
    schema_migrations.create(connection, checkfirst=True)
    connection.commit()
    applied = {
        row.version for row in connection.execute(select(schema_migrations.c.version))
    }
    for migration in sorted(migrations, key=lambda m: m.version):
        if migration.version in applied:
            continue
        logger.info(f"Applying migration {migration.version}: {migration.description}")
        try:
            migration.apply(connection)
            connection.execute(
                schema_migrations.insert().values(
                    version=migration.version, description=migration.description
                )
            )
        except SQLAlchemyError as exc:
            connection.rollback()
            logger.error(
                f"Migration {migration.version} failed and was rolled back: {exc}"
            )
            raise
        else:
            connection.commit()
