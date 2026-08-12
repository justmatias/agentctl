from pathlib import Path
from typing import NamedTuple

import pytest

from agentctl.domain import Binding, Conflict, ConflictResolution, Extension
from agentctl.storage import (
    Database,
    SqliteBindingRepository,
    SqliteConflictRepository,
    SqliteExtensionRepository,
)
from tests.factories import BindingFactory, ExtensionFactory

# SPECS.md §9: the DB is disposable — deleting it and rescanning must
# reproduce the full inventory, losing only DB-only state (user decisions,
# and canonical records not yet bound anywhere).
#
# No adapter exists yet to perform a real scan (that ships in Phase 1), so
# "rescan" here is simulated by re-inserting exactly what discovery of the
# same on-disk state would find.


class DiscoveredInventory(NamedTuple):
    extension: Extension
    binding: Binding
    unbound_extension: Extension


@pytest.fixture
def discovered_inventory(
    database_path: Path,
    extension_factory: ExtensionFactory,
    binding_factory: BindingFactory,
) -> DiscoveredInventory:
    """Populate `database_path` as discovery of the on-disk state would: an
    extension with a binding, an intentionally-kept conflict, and an
    unbound extension. Closes the database before returning.
    """
    database = Database(database_path)
    extension_repository = SqliteExtensionRepository(database.connection)
    binding_repository = SqliteBindingRepository(database.connection)
    conflict_repository = SqliteConflictRepository(database.connection)

    discovered_extension = extension_factory.build(name="github")
    extension_repository.create(discovered_extension)
    discovered_binding = binding_factory.build(extension_id=discovered_extension.id)
    binding_repository.create(discovered_binding)

    unbound_extension = extension_factory.build(name="orphaned")
    extension_repository.create(unbound_extension)

    conflict_repository.create(
        Conflict(
            extension_id=discovered_extension.id,
            binding_ids=[discovered_binding.id],
            resolution=ConflictResolution.KEEP_BOTH_INTENTIONALLY,
        )
    )
    database.close()
    return DiscoveredInventory(discovered_extension, discovered_binding, unbound_extension)


def test_deleting_database_then_rescanning_only_loses_database_only_state(
    database_path: Path, discovered_inventory: DiscoveredInventory
) -> None:
    extension, binding, unbound_extension = discovered_inventory
    database_path.unlink()

    rescanned = Database(database_path)
    rescanned_extensions = SqliteExtensionRepository(rescanned.connection)
    rescanned_bindings = SqliteBindingRepository(rescanned.connection)
    rescanned_conflicts = SqliteConflictRepository(rescanned.connection)

    rescanned_extensions.create(extension)
    rescanned_bindings.create(binding)

    assert rescanned_extensions.get(extension.id) == extension
    assert rescanned_bindings.get(binding.id) == binding

    assert rescanned_extensions.get(unbound_extension.id) is None
    assert rescanned_conflicts.list() == []

    rescanned.close()
