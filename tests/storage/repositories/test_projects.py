from agentctl.domain import Project
from agentctl.storage import SqliteProjectRepository


def test_project_create_and_get_round_trip(
    project_repository: SqliteProjectRepository,
    project_with_detected_sources: Project,
) -> None:
    assert (
        project_repository.get(project_with_detected_sources.id)
        == project_with_detected_sources
    )


def test_project_update_persists_changes(
    project_repository: SqliteProjectRepository,
    saved_project: Project,
) -> None:
    renamed = saved_project.model_copy(update={"display_name": "renamed"})
    project_repository.update(renamed)

    assert project_repository.get(saved_project.id) == renamed


def test_project_list_orders_by_registration(
    project_repository: SqliteProjectRepository,
    earlier_project: Project,
    later_project: Project,
) -> None:
    assert [p.id for p in project_repository.list()] == [
        earlier_project.id,
        later_project.id,
    ]
