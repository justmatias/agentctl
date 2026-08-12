from collections.abc import Callable

from agentctl.domain import Project, Source
from agentctl.storage import SqliteProjectRepository


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
