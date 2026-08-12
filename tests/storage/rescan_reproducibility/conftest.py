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
from tests.polyfactory import BindingFactory, ExtensionFactory


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
    extension_repository = SqliteExtensionRepository(seed_database.session)
    extension = extension_factory.build(name="github")
    extension_repository.create(extension)
    return extension


@pytest.fixture
def discovered_binding(
    seed_database: Database,
    binding_factory: BindingFactory,
    discovered_extension: Extension,
) -> Binding:
    binding_repository = SqliteBindingRepository(seed_database.session)
    binding = binding_factory.build(extension_id=discovered_extension.id)
    binding_repository.create(binding)
    return binding


@pytest.fixture
def unbound_extension(
    seed_database: Database, extension_factory: ExtensionFactory
) -> Extension:
    extension_repository = SqliteExtensionRepository(seed_database.session)
    extension = extension_factory.build(name="orphaned")
    extension_repository.create(extension)
    return extension


@pytest.fixture
def intentionally_kept_conflict(
    seed_database: Database,
    discovered_extension: Extension,
    discovered_binding: Binding,
) -> Conflict:
    conflict_repository = SqliteConflictRepository(seed_database.session)
    conflict = Conflict(
        extension_id=discovered_extension.id,
        binding_ids=[discovered_binding.id],
        resolution=ConflictResolution.KEEP_BOTH_INTENTIONALLY,
    )
    conflict_repository.create(conflict)
    return conflict
