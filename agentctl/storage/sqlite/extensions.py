from agentctl.domain import Extension
from agentctl.storage.schema import ExtensionRow

from .repository import SqliteRepository


class SqliteExtensionRepository(SqliteRepository[Extension, ExtensionRow]):
    _domain_model = Extension
    _row_model = ExtensionRow
    _default_order_by = "created_at"
