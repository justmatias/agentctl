from sqlalchemy import RowMapping, insert, update

from agentctl.domain import Extension

from ..schema import extensions
from .repository import SqliteRepository


class SqliteExtensionRepository(SqliteRepository[Extension]):
    _table = extensions
    _entity_name = "extension"

    def list(self, *, order_by: str | None = None) -> list[Extension]:
        return super().list(order_by=order_by or "created_at")

    def create(self, extension: Extension) -> None:
        self._write(
            insert(extensions).values(
                id=str(extension.id),
                type=extension.type.value,
                name=extension.name,
                origin_harness=(
                    extension.origin_harness.value if extension.origin_harness else None
                ),
                canonical_config=extension.canonical_config.model_dump(mode="json"),
                created_at=extension.created_at.isoformat(),
                updated_at=extension.updated_at.isoformat(),
            ),
            action="Created",
            item_id=extension.id,
        )

    def update(self, extension: Extension) -> None:
        self._write(
            update(extensions)
            .where(extensions.c.id == str(extension.id))
            .values(
                type=extension.type.value,
                name=extension.name,
                origin_harness=(
                    extension.origin_harness.value if extension.origin_harness else None
                ),
                canonical_config=extension.canonical_config.model_dump(mode="json"),
                updated_at=extension.updated_at.isoformat(),
            ),
            action="Updated",
            item_id=extension.id,
        )

    @staticmethod
    def _row_to_model(row: RowMapping) -> Extension:
        return Extension.model_validate(dict(row))
