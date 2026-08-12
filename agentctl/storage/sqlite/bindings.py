from uuid import UUID

from sqlalchemy import RowMapping, insert, select, update

from agentctl.domain import Binding

from ..schema import bindings
from .repository import SqliteRepository


class SqliteBindingRepository(SqliteRepository[Binding]):
    _table = bindings
    _entity_name = "binding"

    def create(self, binding: Binding) -> None:
        self._write(
            insert(bindings).values(
                id=str(binding.id),
                extension_id=str(binding.extension_id),
                harness=binding.harness.value,
                scope=binding.scope.value,
                file_path=binding.file_path,
                enabled=binding.enabled,
                sync_state=binding.sync_state.value,
                last_written_hash=binding.last_written_hash,
                last_seen_hash=binding.last_seen_hash,
            ),
            action="Created",
            item_id=binding.id,
            extra=f" for extension {binding.extension_id}",
        )

    def list_for_extension(self, extension_id: UUID) -> list[Binding]:
        rows = (
            self._connection
            .execute(
                select(bindings).where(bindings.c.extension_id == str(extension_id))
            )
            .mappings()
            .fetchall()
        )
        return [self._row_to_model(row) for row in rows]

    def update(self, binding: Binding) -> None:
        self._write(
            update(bindings)
            .where(bindings.c.id == str(binding.id))
            .values(
                extension_id=str(binding.extension_id),
                harness=binding.harness.value,
                scope=binding.scope.value,
                file_path=binding.file_path,
                enabled=binding.enabled,
                sync_state=binding.sync_state.value,
                last_written_hash=binding.last_written_hash,
                last_seen_hash=binding.last_seen_hash,
            ),
            action="Updated",
            item_id=binding.id,
        )

    @staticmethod
    def _row_to_model(row: RowMapping) -> Binding:
        return Binding.model_validate(dict(row))
