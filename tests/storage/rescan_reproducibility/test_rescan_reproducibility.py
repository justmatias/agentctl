from pathlib import Path

import pytest

from agentctl.domain import Binding, Extension
from agentctl.storage import (
    Database,
    SqliteBindingRepository,
    SqliteConflictRepository,
    SqliteExtensionRepository,
)

# SPECS.md §9: the DB is disposable — deleting it and rescanning must
# reproduce the full inventory, losing only DB-only state (user decisions,
# and canonical records not yet bound anywhere).
#
# No adapter exists yet to perform a real scan (that ships in Phase 1), so
# "rescan" here is simulated by re-inserting exactly what discovery of the
# same on-disk state would find.


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
