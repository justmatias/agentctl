from collections.abc import Callable, Generator
from pathlib import Path

import pytest

from agentctl.domain import Binding, ConsultedLayer, Extension, Project, Source
from agentctl.storage import (
    Database,
    SqliteBindingRepository,
    SqliteConflictRepository,
    SqliteExtensionRepository,
    SqlitePrecedenceChainRepository,
    SqliteProjectRepository,
)
from tests.factories import (
    create_consulted_layer,
    create_saved_binding,
    create_saved_conflict,
    create_saved_extension,
    create_saved_precedence_chain,
    create_saved_project,
)

__all__ = [
    "create_consulted_layer",
    "create_saved_binding",
    "create_saved_conflict",
    "create_saved_extension",
    "create_saved_precedence_chain",
    "create_saved_project",
]


@pytest.fixture
def database() -> Generator[Database]:
    database = Database(":memory:")
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "agentctl.db"


@pytest.fixture
def extension_repository(database: Database) -> SqliteExtensionRepository:
    return SqliteExtensionRepository(database.session)


@pytest.fixture
def binding_repository(database: Database) -> SqliteBindingRepository:
    return SqliteBindingRepository(database.session)


@pytest.fixture
def conflict_repository(database: Database) -> SqliteConflictRepository:
    return SqliteConflictRepository(database.session)


@pytest.fixture
def project_repository(database: Database) -> SqliteProjectRepository:
    return SqliteProjectRepository(database.session)


@pytest.fixture
def precedence_chain_repository(
    database: Database,
) -> SqlitePrecedenceChainRepository:
    return SqlitePrecedenceChainRepository(database.session)


@pytest.fixture
def saved_extension(create_saved_extension: Callable[..., Extension]) -> Extension:
    return create_saved_extension()


@pytest.fixture
def other_extension(create_saved_extension: Callable[..., Extension]) -> Extension:
    return create_saved_extension()


@pytest.fixture
def saved_binding(
    create_saved_binding: Callable[..., Binding], saved_extension: Extension
) -> Binding:
    return create_saved_binding(extension_id=saved_extension.id)


@pytest.fixture
def other_binding(
    create_saved_binding: Callable[..., Binding], other_extension: Extension
) -> Binding:
    return create_saved_binding(extension_id=other_extension.id)


@pytest.fixture
def saved_project(create_saved_project: Callable[..., Project]) -> Project:
    return create_saved_project()


@pytest.fixture
def project_with_detected_sources(
    create_saved_project: Callable[..., Project],
) -> Project:
    return create_saved_project(
        detected_sources=[Source.CLAUDE_CODE, Source.DOT_AGENTS]
    )


@pytest.fixture
def earlier_project(create_saved_project: Callable[..., Project]) -> Project:
    return create_saved_project(path="/home/user/code/a", display_name="a")


@pytest.fixture
def later_project(
    create_saved_project: Callable[..., Project], earlier_project: Project
) -> Project:
    return create_saved_project(path="/home/user/code/b", display_name="b")


@pytest.fixture
def consulted_layer(
    create_consulted_layer: Callable[..., ConsultedLayer],
) -> ConsultedLayer:
    return create_consulted_layer()
