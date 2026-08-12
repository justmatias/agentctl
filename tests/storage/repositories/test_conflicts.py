from agentctl.domain import Binding, Conflict, ConflictResolution, Extension
from agentctl.storage import SqliteConflictRepository


def test_conflict_create_and_get_round_trip(
    conflict_repository: SqliteConflictRepository, saved_binding: Binding
) -> None:
    conflict = Conflict(
        extension_id=saved_binding.extension_id, binding_ids=[saved_binding.id]
    )

    conflict_repository.create(conflict)

    assert conflict_repository.get(conflict.id) == conflict


def test_conflict_keep_both_intentionally_persists(
    conflict_repository: SqliteConflictRepository, saved_extension: Extension
) -> None:
    conflict = Conflict(
        extension_id=saved_extension.id,
        binding_ids=[],
        resolution=ConflictResolution.KEEP_BOTH_INTENTIONALLY,
    )
    conflict_repository.create(conflict)

    reloaded = conflict_repository.get(conflict.id)

    assert reloaded is not None
    assert reloaded.resolution == ConflictResolution.KEEP_BOTH_INTENTIONALLY


def test_conflict_update_persists_resolution(
    conflict_repository: SqliteConflictRepository, saved_binding: Binding
) -> None:
    conflict = Conflict(
        extension_id=saved_binding.extension_id, binding_ids=[saved_binding.id]
    )
    conflict_repository.create(conflict)

    resolved = conflict.model_copy(
        update={
            "resolution": ConflictResolution.SOURCE_CHOSEN,
            "resolved_binding_id": saved_binding.id,
        }
    )
    conflict_repository.update(resolved)

    assert conflict_repository.get(conflict.id) == resolved
