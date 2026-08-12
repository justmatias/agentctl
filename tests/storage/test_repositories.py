from collections.abc import Callable
from uuid import uuid4

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
    create_saved_extension: Callable[..., Extension],
) -> None:
    first = create_saved_extension(name="a")
    second = create_saved_extension(name="b")

    assert {e.id for e in extension_repository.list()} == {first.id, second.id}


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
