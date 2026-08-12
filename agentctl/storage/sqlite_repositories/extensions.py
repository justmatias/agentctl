import json
import sqlite3

from agentctl.domain import Extension

from .base import SqliteRepository


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
