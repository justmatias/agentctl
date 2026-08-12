from collections.abc import Callable
from uuid import uuid4

from agentctl.domain import (
    Binding,
    Conflict,
    ConflictResolution,
    ConsultedLayer,
    Extension,
    PrecedenceChain,
    Project,
    Source,
)
from agentctl.storage import (
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


def test_shared_get_missing_returns_none(
    extension_repository: SqliteExtensionRepository,
) -> None:
    assert extension_repository.get(uuid4()) is None


def test_shared_list_returns_all_created(
    extension_repository: SqliteExtensionRepository,
    extension_factory: ExtensionFactory,
) -> None:
    first = extension_factory.build(name="a")
    second = extension_factory.build(name="b")
    extension_repository.create(first)
    extension_repository.create(second)

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


def test_extension_create_and_get_round_trip(
    extension_repository: SqliteExtensionRepository,
    extension_factory: ExtensionFactory,
) -> None:
    extension = extension_factory.build()

    extension_repository.create(extension)

    assert extension_repository.get(extension.id) == extension


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


def test_conflict_create_and_get_round_trip(
    conflict_repository: SqliteConflictRepository, saved_binding: Binding
) -> None:
    conflict = Conflict(
        extension_id=saved_binding.extension_id, binding_ids=[saved_binding.id]
    )

    conflict_repository.create(conflict)

    assert conflict_repository.get(conflict.id) == conflict


def test_conflict_keep_both_intentionally_persists(
    conflict_repository: SqliteConflictRepository, saved_extension: Extension
) -> None:
    conflict = Conflict(
        extension_id=saved_extension.id,
        binding_ids=[],
        resolution=ConflictResolution.KEEP_BOTH_INTENTIONALLY,
    )
    conflict_repository.create(conflict)

    reloaded = conflict_repository.get(conflict.id)

    assert reloaded is not None
    assert reloaded.resolution == ConflictResolution.KEEP_BOTH_INTENTIONALLY


def test_conflict_update_persists_resolution(
    conflict_repository: SqliteConflictRepository, saved_binding: Binding
) -> None:
    conflict = Conflict(
        extension_id=saved_binding.extension_id, binding_ids=[saved_binding.id]
    )
    conflict_repository.create(conflict)

    resolved = conflict.model_copy(
        update={
            "resolution": ConflictResolution.SOURCE_CHOSEN,
            "resolved_binding_id": saved_binding.id,
        }
    )
    conflict_repository.update(resolved)

    assert conflict_repository.get(conflict.id) == resolved


def test_project_create_and_get_round_trip(
    project_repository: SqliteProjectRepository,
    create_saved_project: Callable[..., Project],
) -> None:
    project = create_saved_project(
        detected_sources=[Source.CLAUDE_CODE, Source.DOT_AGENTS]
    )

    assert project_repository.get(project.id) == project


def test_project_update_persists_changes(
    project_repository: SqliteProjectRepository,
    create_saved_project: Callable[..., Project],
) -> None:
    project = create_saved_project()

    renamed = project.model_copy(update={"display_name": "renamed"})
    project_repository.update(renamed)

    assert project_repository.get(project.id) == renamed


def test_project_list_orders_by_registration(
    project_repository: SqliteProjectRepository,
    create_saved_project: Callable[..., Project],
) -> None:
    first = create_saved_project(path="/home/user/code/a", display_name="a")
    second = create_saved_project(path="/home/user/code/b", display_name="b")

    assert [p.id for p in project_repository.list()] == [first.id, second.id]


# `SqlitePrecedenceChainRepository` is keyed by (source, project_id), not an
# id, so it doesn't fit the shared base tested above.


def test_precedence_chain_upsert_and_get_global_chain(
    precedence_chain_repository: SqlitePrecedenceChainRepository,
    create_consulted_layer: Callable[..., ConsultedLayer],
) -> None:
    chain = PrecedenceChain(source=Source.CLAUDE_CODE, layers=[create_consulted_layer()])

    precedence_chain_repository.upsert(chain)

    assert precedence_chain_repository.get(Source.CLAUDE_CODE, None) == chain


def test_precedence_chain_upsert_and_get_project_chain(
    precedence_chain_repository: SqlitePrecedenceChainRepository,
    create_consulted_layer: Callable[..., ConsultedLayer],
) -> None:
    project_id = uuid4()
    chain = PrecedenceChain(
        source=Source.CLAUDE_CODE,
        project_id=project_id,
        layers=[create_consulted_layer()],
    )

    precedence_chain_repository.upsert(chain)

    assert precedence_chain_repository.get(Source.CLAUDE_CODE, project_id) == chain
    assert precedence_chain_repository.get(Source.CLAUDE_CODE, None) is None


def test_precedence_chain_upsert_replaces_existing_row_for_same_key(
    precedence_chain_repository: SqlitePrecedenceChainRepository,
    create_consulted_layer: Callable[..., ConsultedLayer],
) -> None:
    precedence_chain_repository.upsert(
        PrecedenceChain(
            source=Source.CLAUDE_CODE, layers=[create_consulted_layer(rank=1)]
        )
    )
    precedence_chain_repository.upsert(
        PrecedenceChain(
            source=Source.CLAUDE_CODE, layers=[create_consulted_layer(rank=2)]
        )
    )

    chains = precedence_chain_repository.list()

    assert len(chains) == 1
    layer = chains[0].layers[0]
    assert isinstance(layer, ConsultedLayer)
    assert layer.order_rank == 2


def test_precedence_chain_delete_removes_row(
    precedence_chain_repository: SqlitePrecedenceChainRepository,
    create_consulted_layer: Callable[..., ConsultedLayer],
) -> None:
    precedence_chain_repository.upsert(
        PrecedenceChain(source=Source.CLAUDE_CODE, layers=[create_consulted_layer()])
    )

    precedence_chain_repository.delete(Source.CLAUDE_CODE, None)

    assert precedence_chain_repository.get(Source.CLAUDE_CODE, None) is None
