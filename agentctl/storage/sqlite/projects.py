import json
import sqlite3

from agentctl.domain import Project

from .repository import SqliteRepository


class SqliteProjectRepository(SqliteRepository[Project]):
    _table = "projects"
    _entity_name = "project"

    def list(self, *, order_by: str | None = None) -> list[Project]:
        return super().list(order_by=order_by or "registered_at")

    def create(self, project: Project) -> None:
        self._write(
            """
            INSERT INTO projects (id, path, display_name, registered_at, detected_sources)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(project.id),
                str(project.path),
                project.display_name,
                project.registered_at.isoformat(),
                json.dumps([source.value for source in project.detected_sources]),
            ),
            action="Created",
            item_id=project.id,
            extra=f" ({project.path})",
        )

    def update(self, project: Project) -> None:
        self._write(
            """
            UPDATE projects
            SET path = ?, display_name = ?, detected_sources = ?
            WHERE id = ?
            """,
            (
                str(project.path),
                project.display_name,
                json.dumps([source.value for source in project.detected_sources]),
                str(project.id),
            ),
            action="Updated",
            item_id=project.id,
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Project:
        return Project.model_validate({
            **dict(row),
            "detected_sources": json.loads(row["detected_sources"]),
        })
