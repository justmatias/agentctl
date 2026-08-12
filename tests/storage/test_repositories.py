from uuid import uuid4

from agentctl.domain import (
    Conflict,
    ConflictResolution,
    ConsultedLayer,
    LayerOrigin,
    PrecedenceChain,
    Project,
    Scope,
    Source,
)
from agentctl.storage import (
    Database,
    SqliteBindingRepository,
    SqliteConflictRepository,
    SqliteExtensionRepository,
    SqlitePrecedenceChainRepository,
    SqliteProjectRepository,
)
from tests.factories import BindingFactory, ExtensionFactory

# The shared `SqliteRepository` base's get/list/update/delete behavior is
# exercised once here via `SqliteExtensionRepository`. The repo-specific
# tests below only cover their own create/row-mapping plus whatever is
# unique to them.


def test_shared_get_missing_returns_none(database: Database) -> None:
    repo = SqliteExtensionRepository(database.connection)

    assert repo.get(uuid4()) is None


def test_shared_list_returns_all_created(
    database: Database, extension_factory: ExtensionFactory
) -> None:
    repo = SqliteExtensionRepository(database.connection)
    first = extension_factory.build(name="a")
    second = extension_factory.build(name="b")
    repo.create(first)
    repo.create(second)

    assert {e.id for e in repo.list()} == {first.id, second.id}


def test_shared_update_persists_changes(
    database: Database, extension_factory: ExtensionFactory
) -> None:
    repo = SqliteExtensionRepository(database.connection)
    extension = extension_factory.build()
    repo.create(extension)

    renamed = extension.model_copy(update={"name": "renamed"})
    repo.update(renamed)

    assert repo.get(extension.id) == renamed


def test_shared_delete_removes_row(
    database: Database, extension_factory: ExtensionFactory
) -> None:
    repo = SqliteExtensionRepository(database.connection)
    extension = extension_factory.build()
    repo.create(extension)

    repo.delete(extension.id)

    assert repo.get(extension.id) is None


def test_extension_create_and_get_round_trip(
    database: Database, extension_factory: ExtensionFactory
) -> None:
    repo = SqliteExtensionRepository(database.connection)
    extension = extension_factory.build()

    repo.create(extension)

    assert repo.get(extension.id) == extension


def test_binding_create_and_get_round_trip(
    database: Database,
    extension_factory: ExtensionFactory,
    binding_factory: BindingFactory,
) -> None:
    extension = extension_factory.build()
    SqliteExtensionRepository(database.connection).create(extension)
    repo = SqliteBindingRepository(database.connection)
    binding = binding_factory.build(extension_id=extension.id)

    repo.create(binding)

    assert repo.get(binding.id) == binding


def test_binding_list_for_extension_filters(
    database: Database,
    extension_factory: ExtensionFactory,
    binding_factory: BindingFactory,
) -> None:
    extension = extension_factory.build()
    SqliteExtensionRepository(database.connection).create(extension)
    other_extension = extension_factory.build()
    SqliteExtensionRepository(database.connection).create(other_extension)
    repo = SqliteBindingRepository(database.connection)
    matching = binding_factory.build(extension_id=extension.id)
    other = binding_factory.build(extension_id=other_extension.id)
    repo.create(matching)
    repo.create(other)

    result = repo.list_for_extension(extension.id)

    assert [b.id for b in result] == [matching.id]


def test_binding_update_persists_changes(
    database: Database,
    extension_factory: ExtensionFactory,
    binding_factory: BindingFactory,
) -> None:
    extension = extension_factory.build()
    SqliteExtensionRepository(database.connection).create(extension)
    repo = SqliteBindingRepository(database.connection)
    binding = binding_factory.build(extension_id=extension.id, enabled=True)
    repo.create(binding)

    disabled = binding.model_copy(update={"enabled": False})
    repo.update(disabled)

    assert repo.get(binding.id) == disabled


def test_conflict_create_and_get_round_trip(
    database: Database,
    extension_factory: ExtensionFactory,
    binding_factory: BindingFactory,
) -> None:
    extension = extension_factory.build()
    SqliteExtensionRepository(database.connection).create(extension)
    binding = binding_factory.build(extension_id=extension.id)
    SqliteBindingRepository(database.connection).create(binding)
    repo = SqliteConflictRepository(database.connection)
    conflict = Conflict(extension_id=extension.id, binding_ids=[binding.id])

    repo.create(conflict)

    assert repo.get(conflict.id) == conflict


def test_conflict_keep_both_intentionally_persists(
    database: Database, extension_factory: ExtensionFactory
) -> None:
    extension = extension_factory.build()
    SqliteExtensionRepository(database.connection).create(extension)
    repo = SqliteConflictRepository(database.connection)
    conflict = Conflict(
        extension_id=extension.id,
        binding_ids=[],
        resolution=ConflictResolution.KEEP_BOTH_INTENTIONALLY,
    )
    repo.create(conflict)

    reloaded = repo.get(conflict.id)

    assert reloaded is not None
    assert reloaded.resolution == ConflictResolution.KEEP_BOTH_INTENTIONALLY


def test_conflict_update_persists_resolution(
    database: Database,
    extension_factory: ExtensionFactory,
    binding_factory: BindingFactory,
) -> None:
    extension = extension_factory.build()
    SqliteExtensionRepository(database.connection).create(extension)
    binding = binding_factory.build(extension_id=extension.id)
    SqliteBindingRepository(database.connection).create(binding)
    repo = SqliteConflictRepository(database.connection)
    conflict = Conflict(extension_id=extension.id, binding_ids=[binding.id])
    repo.create(conflict)

    resolved = conflict.model_copy(
        update={
            "resolution": ConflictResolution.SOURCE_CHOSEN,
            "resolved_binding_id": binding.id,
        }
    )
    repo.update(resolved)

    assert repo.get(conflict.id) == resolved


def test_project_create_and_get_round_trip(database: Database) -> None:
    repo = SqliteProjectRepository(database.connection)
    project = Project(
        path="/home/user/code/demo",
        display_name="demo",
        detected_sources=[Source.CLAUDE_CODE, Source.DOT_AGENTS],
    )

    repo.create(project)

    assert repo.get(project.id) == project


def test_project_update_persists_changes(database: Database) -> None:
    repo = SqliteProjectRepository(database.connection)
    project = Project(path="/home/user/code/demo", display_name="demo")
    repo.create(project)

    renamed = project.model_copy(update={"display_name": "renamed"})
    repo.update(renamed)

    assert repo.get(project.id) == renamed


def test_project_list_orders_by_registration(database: Database) -> None:
    repo = SqliteProjectRepository(database.connection)
    first = Project(path="/home/user/code/a", display_name="a")
    second = Project(path="/home/user/code/b", display_name="b")
    repo.create(first)
    repo.create(second)

    assert [p.id for p in repo.list()] == [first.id, second.id]


def _make_layer(*, rank: int = 1) -> ConsultedLayer:
    return ConsultedLayer(
        scope=Scope.USER,
        file_path="~/.claude/settings.json",
        exists=True,
        order_rank=rank,
        origin=LayerOrigin.GLOBAL,
        resolves=True,
    )


# `SqlitePrecedenceChainRepository` is keyed by (source, project_id), not an
# id, so it doesn't fit the shared base tested above.


def test_precedence_chain_upsert_and_get_global_chain(database: Database) -> None:
    repo = SqlitePrecedenceChainRepository(database.connection)
    chain = PrecedenceChain(source=Source.CLAUDE_CODE, layers=[_make_layer()])

    repo.upsert(chain)

    assert repo.get(Source.CLAUDE_CODE, None) == chain


def test_precedence_chain_upsert_and_get_project_chain(database: Database) -> None:
    repo = SqlitePrecedenceChainRepository(database.connection)
    project_id = uuid4()
    chain = PrecedenceChain(
        source=Source.CLAUDE_CODE, project_id=project_id, layers=[_make_layer()]
    )

    repo.upsert(chain)

    assert repo.get(Source.CLAUDE_CODE, project_id) == chain
    assert repo.get(Source.CLAUDE_CODE, None) is None


def test_precedence_chain_upsert_replaces_existing_row_for_same_key(
    database: Database,
) -> None:
    repo = SqlitePrecedenceChainRepository(database.connection)
    repo.upsert(
        PrecedenceChain(source=Source.CLAUDE_CODE, layers=[_make_layer(rank=1)])
    )
    repo.upsert(
        PrecedenceChain(source=Source.CLAUDE_CODE, layers=[_make_layer(rank=2)])
    )

    chains = repo.list()

    assert len(chains) == 1
    layer = chains[0].layers[0]
    assert isinstance(layer, ConsultedLayer)
    assert layer.order_rank == 2


def test_precedence_chain_delete_removes_row(database: Database) -> None:
    repo = SqlitePrecedenceChainRepository(database.connection)
    repo.upsert(PrecedenceChain(source=Source.CLAUDE_CODE, layers=[_make_layer()]))

    repo.delete(Source.CLAUDE_CODE, None)

    assert repo.get(Source.CLAUDE_CODE, None) is None
