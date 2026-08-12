import json
import sqlite3

from agentctl.domain import Extension

from .repository import SqliteRepository


class SqliteExtensionRepository(SqliteRepository[Extension]):
    _table = "extensions"
    _entity_name = "extension"

    def list(self, *, order_by: str | None = None) -> list[Extension]:
        return super().list(order_by=order_by or "created_at")

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
            **dict(row),
            "canonical_config": json.loads(row["canonical_config"]),
        })
