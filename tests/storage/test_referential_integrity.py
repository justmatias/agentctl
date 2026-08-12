from collections.abc import Callable

from agentctl.domain import Binding, Conflict, Extension
from agentctl.storage import (
    SqliteBindingRepository,
    SqliteConflictRepository,
    SqliteExtensionRepository,
)

# extensions.id is the one relation the schema enforces with a real foreign
# key (bindings/conflicts.extension_id, ON DELETE CASCADE) rather than a
# JSON blob, so deleting an Extension must not raise and must take its
# bindings/conflicts with it.


def test_deleting_extension_cascades_to_its_bindings(
    binding_repository: SqliteBindingRepository,
    extension_repository: SqliteExtensionRepository,
    saved_extension: Extension,
    saved_binding: Binding,
) -> None:
    extension_repository.delete(saved_extension.id)

    assert binding_repository.get(saved_binding.id) is None


def test_deleting_extension_cascades_to_its_conflicts(
    conflict_repository: SqliteConflictRepository,
    extension_repository: SqliteExtensionRepository,
    create_saved_conflict: Callable[..., Conflict],
    saved_extension: Extension,
    saved_binding: Binding,
) -> None:
    conflict = create_saved_conflict(
        extension_id=saved_extension.id, binding_ids=[saved_binding.id]
    )

    extension_repository.delete(saved_extension.id)

    assert conflict_repository.get(conflict.id) is None
