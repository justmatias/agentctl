from agentctl.domain import Project
from agentctl.storage import ProjectRow

from .repository import SqliteRepository


class SqliteProjectRepository(SqliteRepository[Project, ProjectRow]):
    _domain_model = Project
    _row_model = ProjectRow
    _default_order_by = "registered_at"
