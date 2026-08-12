import sqlite3
from dataclasses import dataclass

from agentctl.utils import logger


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    sql: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="Orchestration metadata tables",
        sql="""
            CREATE TABLE IF NOT EXISTS extensions (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                origin_harness TEXT,
                canonical_config TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bindings (
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

            CREATE INDEX IF NOT EXISTS idx_bindings_extension_id
                ON bindings(extension_id);

            CREATE TABLE IF NOT EXISTS conflicts (
                id TEXT PRIMARY KEY,
                extension_id TEXT NOT NULL REFERENCES extensions(id),
                binding_ids TEXT NOT NULL,
                resolved_binding_id TEXT,
                resolution TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conflicts_extension_id
                ON conflicts(extension_id);

            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                detected_sources TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS precedence_chains (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                project_id TEXT,
                layers TEXT NOT NULL,
                UNIQUE (source, project_id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_precedence_chains_global_source
                ON precedence_chains(source) WHERE project_id IS NULL;
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
    applied_rows = connection.execute("SELECT version FROM schema_migrations")
    applied = {row[0] for row in applied_rows}
    for migration in sorted(migrations, key=lambda m: m.version):
        if migration.version in applied:
            continue
        logger.info(f"Applying migration {migration.version}: {migration.description}")
        try:
            connection.executescript(migration.sql)
            connection.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                (migration.version, migration.description),
            )
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            logger.error(
                f"Migration {migration.version} failed, DB may be inconsistent: {exc}"
            )
            raise
