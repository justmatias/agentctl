from pathlib import Path

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import ResourceClosedError, SQLAlchemyError

from agentctl.storage import MIGRATIONS, Database
from agentctl.storage.database import create_sqlite_engine
from agentctl.storage.migrations import Migration, apply_migrations

EXPECTED_TABLES = {
    "extensions",
    "bindings",
    "conflicts",
    "projects",
    "precedence_chains",
    "schema_migrations",
}


def test_empty_database_migrates_to_current_schema(database_path: Path) -> None:
    with Database(database_path) as database:
        tables = {
            row[0]
            for row in database.connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            )
        }
        assert EXPECTED_TABLES <= tables

        applied_versions = {
            row[0]
            for row in database.connection.execute(
                text("SELECT version FROM schema_migrations")
            )
        }
        assert applied_versions == {migration.version for migration in MIGRATIONS}


def test_reopening_an_already_migrated_database_does_not_reapply(
    database_path: Path,
) -> None:
    Database(database_path).close()

    with Database(database_path) as database:
        count = database.connection.execute(
            text("SELECT COUNT(*) FROM schema_migrations")
        ).scalar()
        assert count == len(MIGRATIONS)


def test_used_as_a_context_manager(database_path: Path) -> None:
    with Database(database_path) as database:
        database.connection.execute(text("SELECT 1"))

    with pytest.raises(ResourceClosedError):
        database.connection.execute(text("SELECT 1"))


def test_failed_migration_leaves_no_partial_schema_changes(
    database_path: Path,
) -> None:
    """A migration that creates one table then fails creating a second must
    not leave the first one committed — SQLite DDL is transactional, so
    running both statements inside one explicit transaction (rather than
    the old `executescript()`, which auto-commits each statement) means a
    failure rolls back everything the migration already did.
    """

    def _create_table_then_fail(connection: Connection) -> None:
        connection.execute(text("CREATE TABLE table_a (id TEXT PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE table_b (not valid sql here)"))

    broken_migration = Migration(
        version=1, description="intentionally broken", apply=_create_table_then_fail
    )

    engine = create_sqlite_engine(database_path)
    connection = engine.connect()
    try:
        with pytest.raises(SQLAlchemyError):
            apply_migrations(connection, migrations=(broken_migration,))

        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            )
        }
        assert "table_a" not in tables
    finally:
        connection.close()
        engine.dispose()
