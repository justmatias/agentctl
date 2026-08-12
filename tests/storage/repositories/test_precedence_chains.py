from collections.abc import Callable
from uuid import uuid4

from agentctl.domain import ConsultedLayer, PrecedenceChain, Source
from agentctl.storage import SqlitePrecedenceChainRepository

# Keyed by (source, project_id), not an id, so it doesn't fit the shared
# base tested in tests/storage/test_repositories.py.


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
