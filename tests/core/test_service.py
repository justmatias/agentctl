from agentctl.adapters import AdapterRegistry
from agentctl.adapters.fake import NullAdapter
from agentctl.core import CoreService
from agentctl.domain import Source
from agentctl.storage import Database


def test_empty_registry_returns_no_sources(database: Database) -> None:
    service = CoreService(registry=AdapterRegistry(), database=database)

    assert not service.registered_sources()


def test_returns_the_source_of_every_registered_adapter(database: Database) -> None:
    registry = AdapterRegistry()
    registry.register(NullAdapter(Source.CLAUDE_CODE))
    registry.register(NullAdapter(Source.CURSOR))
    service = CoreService(registry=registry, database=database)

    assert set(service.registered_sources()) == {Source.CLAUDE_CODE, Source.CURSOR}
