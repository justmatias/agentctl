"""SQLite implementations of the storage repositories (ROADMAP.md PR 0.2)."""

import json
import sqlite3
from uuid import UUID, uuid4

from agentctl.domain import (
    Binding,
    Conflict,
    Extension,
    PrecedenceChain,
    Project,
    Source,
)


class SqliteExtensionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(self, extension: Extension) -> None:
        self._connection.execute(
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
        )
        self._connection.commit()

    def get(self, extension_id: UUID) -> Extension | None:
        row = self._connection.execute(
            "SELECT * FROM extensions WHERE id = ?", (str(extension_id),)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def list(self) -> list[Extension]:
        rows = self._connection.execute(
            "SELECT * FROM extensions ORDER BY created_at"
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def update(self, extension: Extension) -> None:
        self._connection.execute(
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
        )
        self._connection.commit()

    def delete(self, extension_id: UUID) -> None:
        self._connection.execute(
            "DELETE FROM extensions WHERE id = ?", (str(extension_id),)
        )
        self._connection.commit()

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Extension:
        return Extension.model_validate(
            {
                "id": row["id"],
                "type": row["type"],
                "name": row["name"],
                "origin_harness": row["origin_harness"],
                "canonical_config": json.loads(row["canonical_config"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )


class SqliteBindingRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(self, binding: Binding) -> None:
        self._connection.execute(
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
        )
        self._connection.commit()

    def get(self, binding_id: UUID) -> Binding | None:
        row = self._connection.execute(
            "SELECT * FROM bindings WHERE id = ?", (str(binding_id),)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def list_for_extension(self, extension_id: UUID) -> list[Binding]:
        rows = self._connection.execute(
            "SELECT * FROM bindings WHERE extension_id = ?", (str(extension_id),)
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def list(self) -> list[Binding]:
        rows = self._connection.execute("SELECT * FROM bindings").fetchall()
        return [self._row_to_model(row) for row in rows]

    def update(self, binding: Binding) -> None:
        self._connection.execute(
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
        )
        self._connection.commit()

    def delete(self, binding_id: UUID) -> None:
        self._connection.execute("DELETE FROM bindings WHERE id = ?", (str(binding_id),))
        self._connection.commit()

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Binding:
        return Binding.model_validate(
            {
                "id": row["id"],
                "extension_id": row["extension_id"],
                "harness": row["harness"],
                "scope": row["scope"],
                "file_path": row["file_path"],
                "enabled": bool(row["enabled"]),
                "sync_state": row["sync_state"],
                "last_written_hash": row["last_written_hash"],
                "last_seen_hash": row["last_seen_hash"],
            }
        )


class SqliteConflictRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(self, conflict: Conflict) -> None:
        self._connection.execute(
            """
            INSERT INTO conflicts
                (id, extension_id, binding_ids, resolved_binding_id, resolution)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(conflict.id),
                str(conflict.extension_id),
                json.dumps([str(bid) for bid in conflict.binding_ids]),
                str(conflict.resolved_binding_id) if conflict.resolved_binding_id else None,
                conflict.resolution.value,
            ),
        )
        self._connection.commit()

    def get(self, conflict_id: UUID) -> Conflict | None:
        row = self._connection.execute(
            "SELECT * FROM conflicts WHERE id = ?", (str(conflict_id),)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def list(self) -> list[Conflict]:
        rows = self._connection.execute("SELECT * FROM conflicts").fetchall()
        return [self._row_to_model(row) for row in rows]

    def update(self, conflict: Conflict) -> None:
        self._connection.execute(
            """
            UPDATE conflicts
            SET extension_id = ?, binding_ids = ?, resolved_binding_id = ?, resolution = ?
            WHERE id = ?
            """,
            (
                str(conflict.extension_id),
                json.dumps([str(bid) for bid in conflict.binding_ids]),
                str(conflict.resolved_binding_id) if conflict.resolved_binding_id else None,
                conflict.resolution.value,
                str(conflict.id),
            ),
        )
        self._connection.commit()

    def delete(self, conflict_id: UUID) -> None:
        self._connection.execute("DELETE FROM conflicts WHERE id = ?", (str(conflict_id),))
        self._connection.commit()

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Conflict:
        return Conflict.model_validate(
            {
                "id": row["id"],
                "extension_id": row["extension_id"],
                "binding_ids": json.loads(row["binding_ids"]),
                "resolved_binding_id": row["resolved_binding_id"],
                "resolution": row["resolution"],
            }
        )


class SqliteProjectRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(self, project: Project) -> None:
        self._connection.execute(
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
        )
        self._connection.commit()

    def get(self, project_id: UUID) -> Project | None:
        row = self._connection.execute(
            "SELECT * FROM projects WHERE id = ?", (str(project_id),)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def list(self) -> list[Project]:
        rows = self._connection.execute(
            "SELECT * FROM projects ORDER BY registered_at"
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def update(self, project: Project) -> None:
        self._connection.execute(
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
        )
        self._connection.commit()

    def delete(self, project_id: UUID) -> None:
        self._connection.execute("DELETE FROM projects WHERE id = ?", (str(project_id),))
        self._connection.commit()

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Project:
        return Project.model_validate(
            {
                "id": row["id"],
                "path": row["path"],
                "display_name": row["display_name"],
                "registered_at": row["registered_at"],
                "detected_sources": json.loads(row["detected_sources"]),
            }
        )


class SqlitePrecedenceChainRepository:
    """Stores a cache row per (source, project_id); never the source of truth (SPECS §9)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(self, chain: PrecedenceChain) -> None:
        self.delete(chain.source, chain.project_id)
        self._connection.execute(
            "INSERT INTO precedence_chains (id, source, project_id, layers) VALUES (?, ?, ?, ?)",
            (
                str(uuid4()),
                chain.source.value,
                str(chain.project_id) if chain.project_id else None,
                json.dumps([layer.model_dump(mode="json") for layer in chain.layers]),
            ),
        )
        self._connection.commit()

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
        self._connection.execute(
            "DELETE FROM precedence_chains WHERE source = ? AND project_id IS ?",
            (source.value, str(project_id) if project_id else None),
        )
        self._connection.commit()

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> PrecedenceChain:
        return PrecedenceChain.model_validate(
            {
                "source": row["source"],
                "project_id": row["project_id"],
                "layers": json.loads(row["layers"]),
            }
        )
