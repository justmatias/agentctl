from collections.abc import Callable

from agentctl.domain import Binding, Extension
from agentctl.storage import SqliteBindingRepository
from tests.factories import BindingFactory


def test_binding_create_and_get_round_trip(
    binding_repository: SqliteBindingRepository,
    binding_factory: BindingFactory,
    saved_extension: Extension,
) -> None:
    binding = binding_factory.build(extension_id=saved_extension.id)

    binding_repository.create(binding)

    assert binding_repository.get(binding.id) == binding


def test_binding_list_for_extension_filters(
    binding_repository: SqliteBindingRepository,
    create_saved_extension: Callable[..., Extension],
    create_saved_binding: Callable[..., Binding],
) -> None:
    extension = create_saved_extension()
    other_extension = create_saved_extension()
    matching = create_saved_binding(extension_id=extension.id)
    create_saved_binding(extension_id=other_extension.id)

    result = binding_repository.list_for_extension(extension.id)

    assert [b.id for b in result] == [matching.id]


def test_binding_update_persists_changes(
    binding_repository: SqliteBindingRepository,
    create_saved_binding: Callable[..., Binding],
    saved_extension: Extension,
) -> None:
    binding = create_saved_binding(extension_id=saved_extension.id, enabled=True)

    disabled = binding.model_copy(update={"enabled": False})
    binding_repository.update(disabled)

    assert binding_repository.get(binding.id) == disabled
