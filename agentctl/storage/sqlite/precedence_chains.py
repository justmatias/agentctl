from agentctl.domain import PrecedenceChain
from agentctl.storage.schema import PrecedenceChainRow

from .repository import SqliteRepository


class SqlitePrecedenceChainRepository(
    SqliteRepository[PrecedenceChain, PrecedenceChainRow]
):
    """Cache, never the source of truth (SPECS §9)."""

    _domain_model = PrecedenceChain
    _row_model = PrecedenceChainRow
    _natural_key = ("source", "project_id")
