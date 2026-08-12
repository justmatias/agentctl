from pathlib import Path

from agentctl.domain import Binding, Conflict, ConflictResolution, Extension
from agentctl.storage import (
    Database,
    SqliteBindingRepository,
    SqliteConflictRepository,
    SqliteExtensionRepository,
)
from tests.factories import BindingFactory, ExtensionFactory


def _seed(
    db: Database, extension_factory: ExtensionFactory, binding_factory: BindingFactory
) -> tuple[Extension, Binding, Extension]:
    """Populate `db` as discovery of the on-disk state would: an extension with
    a binding, an intentionally-kept conflict, and an unbound extension.
    """
    extension_repo = SqliteExtensionRepository(db.connection)
    binding_repo = SqliteBindingRepository(db.connection)
    conflict_repo = SqliteConflictRepository(db.connection)

    discovered_extension = extension_factory.build(name="github")
    extension_repo.create(discovered_extension)
    discovered_binding = binding_factory.build(extension_id=discovered_extension.id)
    binding_repo.create(discovered_binding)

    unbound_extension = extension_factory.build(name="orphaned")
    extension_repo.create(unbound_extension)

    conflict_repo.create(
        Conflict(
            extension_id=discovered_extension.id,
            binding_ids=[discovered_binding.id],
            resolution=ConflictResolution.KEEP_BOTH_INTENTIONALLY,
        )
    )
    return discovered_extension, discovered_binding, unbound_extension


class TestDeletingDbThenRescanning:
    """SPECS.md §9: the DB is disposable — deleting it and rescanning must
    reproduce the full inventory, losing only DB-only state (user decisions,
    and canonical records not yet bound anywhere).

    No adapter exists yet to perform a real scan (that ships in Phase 1), so
    "rescan" here is simulated by re-inserting exactly what discovery of the
    same on-disk state would find.
    """

    @staticmethod
    def test_only_db_only_state_is_lost(
        tmp_path: Path,
        extension_factory: ExtensionFactory,
        binding_factory: BindingFactory,
    ) -> None:
        db_path = tmp_path / "agentctl.db"

        db = Database(db_path)
        discovered_extension, discovered_binding, unbound_extension = _seed(
            db, extension_factory, binding_factory
        )
        db.close()

        db_path.unlink()

        rescanned = Database(db_path)
        rescanned_extensions = SqliteExtensionRepository(rescanned.connection)
        rescanned_bindings = SqliteBindingRepository(rescanned.connection)
        rescanned_conflicts = SqliteConflictRepository(rescanned.connection)

        rescanned_extensions.create(discovered_extension)
        rescanned_bindings.create(discovered_binding)

        assert rescanned_extensions.get(discovered_extension.id) == discovered_extension
        assert rescanned_bindings.get(discovered_binding.id) == discovered_binding

        assert rescanned_extensions.get(unbound_extension.id) is None
        assert rescanned_conflicts.list() == []

        rescanned.close()
