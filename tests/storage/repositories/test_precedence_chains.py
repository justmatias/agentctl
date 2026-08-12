from collections.abc import Callable
from uuid import uuid4

from agentctl.domain import ConsultedLayer, PrecedenceChain, Source
from agentctl.storage import SqlitePrecedenceChainRepository

# Keyed by (source, project_id), not an id, so it doesn't fit the shared
# base tested in tests/storage/test_repositories.py.


def test_precedence_chain_upsert_and_get_global_chain(
    precedence_chain_repository: SqlitePrecedenceChainRepository,
    create_saved_precedence_chain: Callable[..., PrecedenceChain],
    consulted_layer: ConsultedLayer,
) -> None:
    chain = create_saved_precedence_chain(layers=[consulted_layer])

    found = precedence_chain_repository.find_one(
        source=Source.CLAUDE_CODE, project_id=None
    )

    assert found == chain


def test_precedence_chain_upsert_and_get_project_chain(
    precedence_chain_repository: SqlitePrecedenceChainRepository,
    create_saved_precedence_chain: Callable[..., PrecedenceChain],
    consulted_layer: ConsultedLayer,
) -> None:
    project_id = uuid4()
    chain = create_saved_precedence_chain(
        project_id=project_id, layers=[consulted_layer]
    )

    found_project_chain = precedence_chain_repository.find_one(
        source=Source.CLAUDE_CODE, project_id=project_id
    )
    found_global_chain = precedence_chain_repository.find_one(
        source=Source.CLAUDE_CODE, project_id=None
    )

    assert found_project_chain == chain
    assert found_global_chain is None


def test_precedence_chain_upsert_replaces_existing_row_for_same_key(
    precedence_chain_repository: SqlitePrecedenceChainRepository,
    create_saved_precedence_chain: Callable[..., PrecedenceChain],
    create_consulted_layer: Callable[..., ConsultedLayer],
) -> None:
    create_saved_precedence_chain(layers=[create_consulted_layer(rank=1)])
    create_saved_precedence_chain(layers=[create_consulted_layer(rank=2)])

    chains = precedence_chain_repository.list()

    assert len(chains) == 1
    layer = chains[0].layers[0]
    assert isinstance(layer, ConsultedLayer)
    assert layer.order_rank == 2


def test_precedence_chain_delete_removes_row(
    precedence_chain_repository: SqlitePrecedenceChainRepository,
    create_saved_precedence_chain: Callable[..., PrecedenceChain],
    consulted_layer: ConsultedLayer,
) -> None:
    create_saved_precedence_chain(layers=[consulted_layer])

    precedence_chain_repository.delete_where(source=Source.CLAUDE_CODE, project_id=None)

    found = precedence_chain_repository.find_one(
        source=Source.CLAUDE_CODE, project_id=None
    )

    assert found is None
