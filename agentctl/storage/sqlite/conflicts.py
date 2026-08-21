from agentctl.domain import Conflict
from agentctl.storage import ConflictRow

from .repository import SqliteRepository


class SqliteConflictRepository(SqliteRepository[Conflict, ConflictRow]):
    _domain_model = Conflict
    _row_model = ConflictRow
