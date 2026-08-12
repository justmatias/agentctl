import sqlite3
from uuid import UUID

from agentctl.domain import Binding

from .base import SqliteRepository


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
