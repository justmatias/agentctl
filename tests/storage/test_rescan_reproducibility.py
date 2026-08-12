from collections.abc import Generator
from pathlib import Path

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


@pytest.fixture
def seed_database(database_path: Path) -> Generator[Database]:
    """A file-backed database the test closes explicitly mid-test (to delete
    and reopen it); the `finally` here is a no-op safety net for that case.
    """
    database = Database(database_path)
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def discovered_extension(
    seed_database: Database, extension_factory: ExtensionFactory
) -> Extension:
    extension_repository = SqliteExtensionRepository(seed_database.connection)
    extension = extension_factory.build(name="github")
    extension_repository.create(extension)
    return extension


@pytest.fixture
def discovered_binding(
    seed_database: Database,
    binding_factory: BindingFactory,
    discovered_extension: Extension,
) -> Binding:
    binding_repository = SqliteBindingRepository(seed_database.connection)
    binding = binding_factory.build(extension_id=discovered_extension.id)
    binding_repository.create(binding)
    return binding


@pytest.fixture
def unbound_extension(
    seed_database: Database, extension_factory: ExtensionFactory
) -> Extension:
    extension_repository = SqliteExtensionRepository(seed_database.connection)
    extension = extension_factory.build(name="orphaned")
    extension_repository.create(extension)
    return extension


@pytest.fixture
def intentionally_kept_conflict(
    seed_database: Database,
    discovered_extension: Extension,
    discovered_binding: Binding,
) -> Conflict:
    conflict_repository = SqliteConflictRepository(seed_database.connection)
    conflict = Conflict(
        extension_id=discovered_extension.id,
        binding_ids=[discovered_binding.id],
        resolution=ConflictResolution.KEEP_BOTH_INTENTIONALLY,
    )
    conflict_repository.create(conflict)
    return conflict


@pytest.mark.usefixtures("intentionally_kept_conflict")
def test_deleting_database_then_rescanning_only_loses_database_only_state(
    seed_database: Database,
    database_path: Path,
    discovered_extension: Extension,
    discovered_binding: Binding,
    unbound_extension: Extension,
) -> None:
    seed_database.close()
    database_path.unlink()

    rescanned = Database(database_path)
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
