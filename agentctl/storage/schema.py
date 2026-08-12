"""SQLAlchemy Core table definitions — the single source of truth for the
on-disk schema, used by both `migrations.py` (DDL) and the repositories
(DML), replacing the old hand-written CREATE TABLE / INSERT / UPDATE SQL.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    text,
)

metadata = MetaData()

extensions = Table(
    "extensions",
    metadata,
    Column("id", String, primary_key=True),
    Column("type", String, nullable=False),
    Column("name", String, nullable=False),
    Column("origin_harness", String),
    Column("canonical_config", JSON, nullable=False),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

# `extension_id` cascades: an Extension's bindings/conflicts have no meaning
# once the Extension is gone, and SPECS.md §9 treats the DB as disposable.
# `binding_ids`/`layers` below stay JSON blobs, not join tables, so their
# references aren't relationally enforced — a pre-existing, deliberate
# denormalization (SPECS.md §8), not something this schema tries to fix.
bindings = Table(
    "bindings",
    metadata,
    Column(
        "id",
        String,
        primary_key=True,
    ),
    Column(
        "extension_id",
        String,
        ForeignKey("extensions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("harness", String, nullable=False),
    Column("scope", String, nullable=False),
    Column("file_path", String, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("sync_state", String, nullable=False),
    Column("last_written_hash", String),
    Column("last_seen_hash", String),
    Index("idx_bindings_extension_id", "extension_id"),
)

conflicts = Table(
    "conflicts",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "extension_id",
        String,
        ForeignKey("extensions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("binding_ids", JSON, nullable=False),
    Column("resolved_binding_id", String),
    Column("resolution", String, nullable=False),
    Index("idx_conflicts_extension_id", "extension_id"),
)

projects = Table(
    "projects",
    metadata,
    Column("id", String, primary_key=True),
    Column("path", String, nullable=False, unique=True),
    Column("display_name", String, nullable=False),
    Column("registered_at", String, nullable=False),
    Column("detected_sources", JSON, nullable=False),
)

precedence_chains = Table(
    "precedence_chains",
    metadata,
    Column("id", String, primary_key=True),
    Column("source", String, nullable=False),
    Column("project_id", String),
    Column("layers", JSON, nullable=False),
    UniqueConstraint("source", "project_id"),
)

Index(
    "idx_precedence_chains_global_source",
    precedence_chains.c.source,
    unique=True,
    sqlite_where=precedence_chains.c.project_id.is_(None),
)

schema_migrations = Table(
    "schema_migrations",
    metadata,
    Column("version", Integer, primary_key=True),
    Column("description", String, nullable=False),
    Column(
        "applied_at", String, nullable=False, server_default=text("(datetime('now'))")
    ),
)
