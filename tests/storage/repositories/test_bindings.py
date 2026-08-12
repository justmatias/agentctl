from agentctl.domain import Binding, Extension
from agentctl.storage import SqliteBindingRepository
from tests.polyfactory import BindingFactory


def test_binding_create_and_get_round_trip(
    binding_repository: SqliteBindingRepository,
    binding_factory: BindingFactory,
    saved_extension: Extension,
) -> None:
    binding = binding_factory.build(extension_id=saved_extension.id)

    binding_repository.create(binding)

    assert binding_repository.get(binding.id) == binding


def test_binding_find_by_extension_filters(
    binding_repository: SqliteBindingRepository,
    saved_extension: Extension,
    saved_binding: Binding,
    other_binding: Binding,  # pylint: disable=unused-argument
) -> None:
    result = binding_repository.find(extension_id=saved_extension.id)

    assert [binding.id for binding in result] == [saved_binding.id]


def test_binding_update_persists_changes(
    binding_repository: SqliteBindingRepository,
    saved_binding: Binding,
) -> None:
    disabled = saved_binding.model_copy(update={"enabled": False})
    binding_repository.update(disabled)

    assert binding_repository.get(saved_binding.id) == disabled
