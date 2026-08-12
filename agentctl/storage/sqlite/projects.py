from sqlalchemy import RowMapping, insert, update

from agentctl.domain import Project

from ..schema import projects
from .repository import SqliteRepository


class SqliteProjectRepository(SqliteRepository[Project]):
    _table = projects
    _entity_name = "project"

    def list(self, *, order_by: str | None = None) -> list[Project]:
        return super().list(order_by=order_by or "registered_at")

    def create(self, project: Project) -> None:
        self._write(
            insert(projects).values(
                id=str(project.id),
                path=str(project.path),
                display_name=project.display_name,
                registered_at=project.registered_at.isoformat(),
                detected_sources=[source.value for source in project.detected_sources],
            ),
            action="Created",
            item_id=project.id,
            extra=f" ({project.path})",
        )

    def update(self, project: Project) -> None:
        self._write(
            update(projects)
            .where(projects.c.id == str(project.id))
            .values(
                path=str(project.path),
                display_name=project.display_name,
                detected_sources=[source.value for source in project.detected_sources],
            ),
            action="Updated",
            item_id=project.id,
        )

    @staticmethod
    def _row_to_model(row: RowMapping) -> Project:
        return Project.model_validate(dict(row))
