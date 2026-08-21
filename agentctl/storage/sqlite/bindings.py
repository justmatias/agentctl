from agentctl.domain import Binding
from agentctl.storage import BindingRow

from .repository import SqliteRepository


class SqliteBindingRepository(SqliteRepository[Binding, BindingRow]):
    _domain_model = Binding
    _row_model = BindingRow
