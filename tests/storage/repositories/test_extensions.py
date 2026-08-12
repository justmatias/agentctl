from agentctl.storage import SqliteExtensionRepository
from tests.factories import ExtensionFactory


def test_extension_create_and_get_round_trip(
    extension_repository: SqliteExtensionRepository,
    extension_factory: ExtensionFactory,
) -> None:
    extension = extension_factory.build()

    extension_repository.create(extension)

    assert extension_repository.get(extension.id) == extension
