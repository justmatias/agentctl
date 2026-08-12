import json
import sqlite3
from abc import ABC, abstractmethod
from typing import ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel

from agentctl.domain import (
    Binding,
    Conflict,
    Extension,
    PrecedenceChain,
    Project,
    Source,
)
from agentctl.utils import logger


class SqliteRepository[ModelT: BaseModel](ABC):
    """Shared CRUD for repositories keyed by a single `id` column.

    Subclasses supply the table name, row<->model mapping, and the
    insert/update statements (columns differ too much per model to
    generalize those), and get `get`/`list`/`delete` plus the
    commit+log wrapping for writes for free.
    """

    _table: ClassVar[str]
    _entity_name: ClassVar[str]
    _list_order_by: ClassVar[str | None] = None

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, item_id: UUID) -> ModelT | None:
        row = self._connection.execute(
            f"SELECT * FROM {self._table} WHERE id = ?", (str(item_id),)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def list(self) -> list[ModelT]:
        query = f"SELECT * FROM {self._table}"
        if self._list_order_by:
            query += f" ORDER BY {self._list_order_by}"
        rows = self._connection.execute(query).fetchall()
        return [self._row_to_model(row) for row in rows]

    def delete(self, item_id: UUID) -> None:
        self._write(
            f"DELETE FROM {self._table} WHERE id = ?",
            (str(item_id),),
            action="Deleted",
            item_id=item_id,
        )

    def _write(
        self,
        sql: str,
        params: tuple[object, ...],
        *,
        action: str,
        item_id: object,
        extra: str = "",
    ) -> None:
        with self._connection:
            self._connection.execute(sql, params)
        logger.info(f"{action} {self._entity_name} {item_id}{extra}")

    @staticmethod
    @abstractmethod
    def _row_to_model(row: sqlite3.Row) -> ModelT: ...


class SqliteExtensionRepository(SqliteRepository[Extension]):
    _table = "extensions"
    _entity_name = "extension"
    _list_order_by = "created_at"

    def create(self, extension: Extension) -> None:
        self._write(
            """
            INSERT INTO extensions
                (id, type, name, origin_harness, canonical_config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(extension.id),
                extension.type.value,
                extension.name,
                extension.origin_harness.value if extension.origin_harness else None,
                extension.canonical_config.model_dump_json(),
                extension.created_at.isoformat(),
                extension.updated_at.isoformat(),
            ),
            action="Created",
            item_id=extension.id,
        )

    def update(self, extension: Extension) -> None:
        self._write(
            """
            UPDATE extensions
            SET type = ?, name = ?, origin_harness = ?, canonical_config = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                extension.type.value,
                extension.name,
                extension.origin_harness.value if extension.origin_harness else None,
                extension.canonical_config.model_dump_json(),
                extension.updated_at.isoformat(),
                str(extension.id),
            ),
            action="Updated",
            item_id=extension.id,
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Extension:
        return Extension.model_validate({
            "id": row["id"],
            "type": row["type"],
            "name": row["name"],
            "origin_harness": row["origin_harness"],
            "canonical_config": json.loads(row["canonical_config"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })


class SqliteBindingRepository(SqliteRepository[Binding]):
    _table = "bindings"
    _entity_name = "binding"

    def create(self, binding: Binding) -> None:
        self._write(
            """
            INSERT INTO bindings
                (id, extension_id, harness, scope, file_path, enabled,
                 sync_state, last_written_hash, last_seen_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(binding.id),
                str(binding.extension_id),
                binding.harness.value,
                binding.scope.value,
                binding.file_path,
                int(binding.enabled),
                binding.sync_state.value,
                binding.last_written_hash,
                binding.last_seen_hash,
            ),
            action="Created",
            item_id=binding.id,
            extra=f" for extension {binding.extension_id}",
        )

    def list_for_extension(self, extension_id: UUID) -> list[Binding]:
        rows = self._connection.execute(
            "SELECT * FROM bindings WHERE extension_id = ?", (str(extension_id),)
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def update(self, binding: Binding) -> None:
        self._write(
            """
            UPDATE bindings
            SET extension_id = ?, harness = ?, scope = ?, file_path = ?, enabled = ?,
                sync_state = ?, last_written_hash = ?, last_seen_hash = ?
            WHERE id = ?
            """,
            (
                str(binding.extension_id),
                binding.harness.value,
                binding.scope.value,
                binding.file_path,
                int(binding.enabled),
                binding.sync_state.value,
                binding.last_written_hash,
                binding.last_seen_hash,
                str(binding.id),
            ),
            action="Updated",
            item_id=binding.id,
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Binding:
        return Binding.model_validate({
            "id": row["id"],
            "extension_id": row["extension_id"],
            "harness": row["harness"],
            "scope": row["scope"],
            "file_path": row["file_path"],
            "enabled": bool(row["enabled"]),
            "sync_state": row["sync_state"],
            "last_written_hash": row["last_written_hash"],
            "last_seen_hash": row["last_seen_hash"],
        })


class SqliteConflictRepository(SqliteRepository[Conflict]):
    _table = "conflicts"
    _entity_name = "conflict"

    def create(self, conflict: Conflict) -> None:
        self._write(
            """
            INSERT INTO conflicts
                (id, extension_id, binding_ids, resolved_binding_id, resolution)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(conflict.id),
                str(conflict.extension_id),
                json.dumps([str(bid) for bid in conflict.binding_ids]),
                str(conflict.resolved_binding_id)
                if conflict.resolved_binding_id
                else None,
                conflict.resolution.value,
            ),
            action="Created",
            item_id=conflict.id,
            extra=f" for extension {conflict.extension_id}",
        )

    def update(self, conflict: Conflict) -> None:
        self._write(
            """
            UPDATE conflicts
            SET extension_id = ?, binding_ids = ?, resolved_binding_id = ?, resolution = ?
            WHERE id = ?
            """,
            (
                str(conflict.extension_id),
                json.dumps([str(bid) for bid in conflict.binding_ids]),
                str(conflict.resolved_binding_id)
                if conflict.resolved_binding_id
                else None,
                conflict.resolution.value,
                str(conflict.id),
            ),
            action="Updated",
            item_id=conflict.id,
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Conflict:
        return Conflict.model_validate({
            "id": row["id"],
            "extension_id": row["extension_id"],
            "binding_ids": json.loads(row["binding_ids"]),
            "resolved_binding_id": row["resolved_binding_id"],
            "resolution": row["resolution"],
        })


class SqliteProjectRepository(SqliteRepository[Project]):
    _table = "projects"
    _entity_name = "project"
    _list_order_by = "registered_at"

    def create(self, project: Project) -> None:
        self._write(
            """
            INSERT INTO projects (id, path, display_name, registered_at, detected_sources)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(project.id),
                str(project.path),
                project.display_name,
                project.registered_at.isoformat(),
                json.dumps([source.value for source in project.detected_sources]),
            ),
            action="Created",
            item_id=project.id,
            extra=f" ({project.path})",
        )

    def update(self, project: Project) -> None:
        self._write(
            """
            UPDATE projects
            SET path = ?, display_name = ?, detected_sources = ?
            WHERE id = ?
            """,
            (
                str(project.path),
                project.display_name,
                json.dumps([source.value for source in project.detected_sources]),
                str(project.id),
            ),
            action="Updated",
            item_id=project.id,
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Project:
        return Project.model_validate({
            "id": row["id"],
            "path": row["path"],
            "display_name": row["display_name"],
            "registered_at": row["registered_at"],
            "detected_sources": json.loads(row["detected_sources"]),
        })


class SqlitePrecedenceChainRepository:
    """Stores a cache row per (source, project_id); never the source of truth
    (SPECS §9).

    Not a `SqliteRepository`: it's keyed by (source, project_id) rather than
    an id, and has `upsert` instead of `create`/`update`.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(self, chain: PrecedenceChain) -> None:
        with self._connection:
            self._connection.execute(
                "DELETE FROM precedence_chains WHERE source = ? AND project_id IS ?",
                (
                    chain.source.value,
                    str(chain.project_id) if chain.project_id else None,
                ),
            )
            self._connection.execute(
                """
                INSERT INTO precedence_chains (id, source, project_id, layers)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    chain.source.value,
                    str(chain.project_id) if chain.project_id else None,
                    json.dumps([
                        layer.model_dump(mode="json") for layer in chain.layers
                    ]),
                ),
            )
        logger.info(
            f"Upserted precedence chain for source {chain.source.value} "
            f"(project {chain.project_id})"
        )

    def get(self, source: Source, project_id: UUID | None) -> PrecedenceChain | None:
        row = self._connection.execute(
            "SELECT * FROM precedence_chains WHERE source = ? AND project_id IS ?",
            (source.value, str(project_id) if project_id else None),
        ).fetchone()
        return self._row_to_model(row) if row else None

    def list(self) -> list[PrecedenceChain]:
        rows = self._connection.execute("SELECT * FROM precedence_chains").fetchall()
        return [self._row_to_model(row) for row in rows]

    def delete(self, source: Source, project_id: UUID | None) -> None:
        with self._connection:
            self._connection.execute(
                "DELETE FROM precedence_chains WHERE source = ? AND project_id IS ?",
                (source.value, str(project_id) if project_id else None),
            )
        logger.info(
            f"Deleted precedence chain for source {source.value} (project {project_id})"
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> PrecedenceChain:
        return PrecedenceChain.model_validate({
            "source": row["source"],
            "project_id": row["project_id"],
            "layers": json.loads(row["layers"]),
        })
