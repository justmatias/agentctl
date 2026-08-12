"""SQLModel row definitions — the single source of truth for the on-disk
schema, used by both `migrations.py` (DDL) and the repositories (DML).
"""

from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel


class ExtensionRow(SQLModel, table=True):
    __tablename__ = "extensions"

    id: str = Field(primary_key=True)
    type: str
    name: str
    origin_harness: str | None = None
    canonical_config: dict[str, Any] = Field(sa_type=JSON)
    created_at: str
    updated_at: str


# `extension_id` cascades: an Extension's bindings/conflicts have no meaning
# once the Extension is gone, and SPECS.md §9 treats the DB as disposable.
# `binding_ids`/`layers` below stay JSON blobs, not join tables, so their
# references aren't relationally enforced — a pre-existing, deliberate
# denormalization (SPECS.md §8), not something this schema tries to fix.
class BindingRow(SQLModel, table=True):
    __tablename__ = "bindings"
    __table_args__ = (Index("idx_bindings_extension_id", "extension_id"),)

    id: str = Field(primary_key=True)
    extension_id: str = Field(foreign_key="extensions.id", ondelete="CASCADE")
    harness: str
    scope: str
    file_path: str
    enabled: bool
    sync_state: str
    last_written_hash: str | None = None
    last_seen_hash: str | None = None


class ConflictRow(SQLModel, table=True):
    __tablename__ = "conflicts"
    __table_args__ = (Index("idx_conflicts_extension_id", "extension_id"),)

    id: str = Field(primary_key=True)
    extension_id: str = Field(foreign_key="extensions.id", ondelete="CASCADE")
    binding_ids: list[str] = Field(sa_type=JSON)
    resolved_binding_id: str | None = None
    resolution: str


class ProjectRow(SQLModel, table=True):
    __tablename__ = "projects"

    id: str = Field(primary_key=True)
    path: str = Field(unique=True)
    display_name: str
    registered_at: str
    detected_sources: list[str] = Field(sa_type=JSON)


class PrecedenceChainRow(SQLModel, table=True):
    """Cache, never the source of truth (SPECS §9)."""

    __tablename__ = "precedence_chains"
    __table_args__ = (
        UniqueConstraint("source", "project_id"),
        Index(
            "idx_precedence_chains_global_source",
            "source",
            unique=True,
            sqlite_where=text("project_id IS NULL"),
        ),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    source: str
    project_id: str | None = None
    layers: list[dict[str, Any]] = Field(sa_type=JSON)


class SchemaMigrationRow(SQLModel, table=True):
    __tablename__ = "schema_migrations"

    version: int = Field(primary_key=True)
    description: str
    applied_at: str = Field(
        sa_column_kwargs={"server_default": text("(datetime('now'))")}
    )
