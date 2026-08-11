"""Linear versioned-DDL migration runner (ROADMAP.md PR 0.2)."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    sql: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="Phase-0 orchestration metadata tables",
        sql="""
            CREATE TABLE extensions (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                origin_harness TEXT,
                canonical_config TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE bindings (
                id TEXT PRIMARY KEY,
                extension_id TEXT NOT NULL REFERENCES extensions(id),
                harness TEXT NOT NULL,
                scope TEXT NOT NULL,
                file_path TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                sync_state TEXT NOT NULL,
                last_written_hash TEXT,
                last_seen_hash TEXT
            );

            CREATE TABLE conflicts (
                id TEXT PRIMARY KEY,
                extension_id TEXT NOT NULL REFERENCES extensions(id),
                binding_ids TEXT NOT NULL,
                resolved_binding_id TEXT,
                resolution TEXT NOT NULL
            );

            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                detected_sources TEXT NOT NULL
            );

            CREATE TABLE precedence_chains (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                project_id TEXT,
                layers TEXT NOT NULL,
                UNIQUE (source, project_id)
            );
        """,
    ),
)


def apply_migrations(
    connection: sqlite3.Connection, migrations: tuple[Migration, ...] = MIGRATIONS
) -> None:
    """Apply every migration not yet recorded in `schema_migrations`, in order."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    applied = {
        row[0]
        for row in connection.execute("SELECT version FROM schema_migrations")
    }
    for migration in sorted(migrations, key=lambda m: m.version):
        if migration.version in applied:
            continue
        connection.executescript(migration.sql)
        connection.execute(
            "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
            (migration.version, migration.description),
        )
    connection.commit()
