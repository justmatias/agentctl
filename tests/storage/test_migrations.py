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


class TestMigrations:
    @staticmethod
    def test_empty_db_migrates_to_current_schema(tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        try:
            tables = {
                row[0]
                for row in db.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            assert EXPECTED_TABLES <= tables

            applied_versions = {
                row[0]
                for row in db.connection.execute(
                    "SELECT version FROM schema_migrations"
                )
            }
            assert applied_versions == {migration.version for migration in MIGRATIONS}
        finally:
            db.close()

    @staticmethod
    def test_reopening_an_already_migrated_db_does_not_reapply(
        tmp_path: Path,
    ) -> None:
        db_path = tmp_path / "test.db"
        Database(db_path).close()

        db = Database(db_path)
        try:
            count = db.connection.execute(
                "SELECT COUNT(*) FROM schema_migrations"
            ).fetchone()[0]
            assert count == len(MIGRATIONS)
        finally:
            db.close()

    @staticmethod
    def test_used_as_a_context_manager(tmp_path: Path) -> None:
        with Database(tmp_path / "test.db") as db:
            db.connection.execute("SELECT 1")

        with pytest.raises(sqlite3.ProgrammingError):
            db.connection.execute("SELECT 1")
