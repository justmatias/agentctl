from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from agentctl.domain import Extension
from agentctl.storage import SqliteExtensionRepository

# The shared `SqliteRepository` base's get/list/update/delete behavior is
# exercised once here via `SqliteExtensionRepository`. Per-repository tests
# (create/row-mapping and whatever else is unique to them) live under
# tests/storage/repositories/.


def test_shared_get_missing_returns_none(
    extension_repository: SqliteExtensionRepository,
) -> None:
    assert extension_repository.get(uuid4()) is None


def test_shared_list_returns_all_created(
    extension_repository: SqliteExtensionRepository,
    saved_extension: Extension,
    other_extension: Extension,
) -> None:
    assert {extension.id for extension in extension_repository.list()} == {
        saved_extension.id,
        other_extension.id,
    }


def test_shared_update_persists_changes(
    extension_repository: SqliteExtensionRepository, saved_extension: Extension
) -> None:
    renamed = saved_extension.model_copy(update={"name": "renamed"})
    extension_repository.update(renamed)

    assert extension_repository.get(saved_extension.id) == renamed


def test_shared_delete_removes_row(
    extension_repository: SqliteExtensionRepository, saved_extension: Extension
) -> None:
    extension_repository.delete(saved_extension.id)

    assert extension_repository.get(saved_extension.id) is None


def test_shared_list_rejects_unknown_order_by_column(
    extension_repository: SqliteExtensionRepository,
) -> None:
    # order_by is resolved against the table's actual columns rather than
    # interpolated into SQL, so a value that isn't a real column name fails
    # closed instead of being executed.
    with pytest.raises(KeyError):
        extension_repository.list(order_by="id; DROP TABLE extensions; --")


def test_shared_create_rolls_back_and_leaves_connection_usable_on_failure(
    extension_repository: SqliteExtensionRepository, saved_extension: Extension
) -> None:
    # Inserting the same id twice violates the primary key, forcing
    # `_write_in_transaction`'s rollback path. The connection must still be
    # usable afterward, and the original row must be untouched.
    with pytest.raises(IntegrityError):
        extension_repository.create(saved_extension)

    assert extension_repository.get(saved_extension.id) == saved_extension
