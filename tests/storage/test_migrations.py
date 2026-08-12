import sqlite3
from pathlib import Path

import pytest

from agentctl.storage import MIGRATIONS, Database

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
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert EXPECTED_TABLES <= tables

        applied_versions = {
            row[0]
            for row in database.connection.execute(
                "SELECT version FROM schema_migrations"
            )
        }
        assert applied_versions == {migration.version for migration in MIGRATIONS}


def test_reopening_an_already_migrated_database_does_not_reapply(
    database_path: Path,
) -> None:
    Database(database_path).close()

    with Database(database_path) as database:
        count = database.connection.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0]
        assert count == len(MIGRATIONS)


def test_used_as_a_context_manager(database_path: Path) -> None:
    with Database(database_path) as database:
        database.connection.execute("SELECT 1")

    with pytest.raises(sqlite3.ProgrammingError):
        database.connection.execute("SELECT 1")
