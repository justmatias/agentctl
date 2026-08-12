from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from agentctl.domain import (
    Binding,
    ConsultedLayer,
    Extension,
    LayerOrigin,
    Project,
    Scope,
)
from agentctl.storage import (
    Database,
    SqliteBindingRepository,
    SqliteConflictRepository,
    SqliteExtensionRepository,
    SqlitePrecedenceChainRepository,
    SqliteProjectRepository,
)
from tests.factories import BindingFactory, ExtensionFactory


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
    return SqliteExtensionRepository(database.connection)


@pytest.fixture
def binding_repository(database: Database) -> SqliteBindingRepository:
    return SqliteBindingRepository(database.connection)


@pytest.fixture
def conflict_repository(database: Database) -> SqliteConflictRepository:
    return SqliteConflictRepository(database.connection)


@pytest.fixture
def project_repository(database: Database) -> SqliteProjectRepository:
    return SqliteProjectRepository(database.connection)


@pytest.fixture
def precedence_chain_repository(
    database: Database,
) -> SqlitePrecedenceChainRepository:
    return SqlitePrecedenceChainRepository(database.connection)


@pytest.fixture
def create_saved_extension(
    extension_repository: SqliteExtensionRepository,
    extension_factory: ExtensionFactory,
) -> Callable[..., Extension]:
    def _create_saved_extension(**overrides: Any) -> Extension:
        extension = extension_factory.build(**overrides)
        extension_repository.create(extension)
        return extension

    return _create_saved_extension


@pytest.fixture
def saved_extension(create_saved_extension: Callable[..., Extension]) -> Extension:
    return create_saved_extension()


@pytest.fixture
def create_saved_binding(
    binding_repository: SqliteBindingRepository,
    binding_factory: BindingFactory,
) -> Callable[..., Binding]:
    def _create_saved_binding(*, extension_id: UUID, **overrides: Any) -> Binding:
        binding = binding_factory.build(extension_id=extension_id, **overrides)
        binding_repository.create(binding)
        return binding

    return _create_saved_binding


@pytest.fixture
def saved_binding(
    create_saved_binding: Callable[..., Binding], saved_extension: Extension
) -> Binding:
    return create_saved_binding(extension_id=saved_extension.id)


@pytest.fixture
def create_saved_project(
    project_repository: SqliteProjectRepository,
) -> Callable[..., Project]:
    def _create_saved_project(
        *,
        path: str = "/home/user/code/demo",
        display_name: str = "demo",
        **overrides: object,
    ) -> Project:
        project = Project(path=path, display_name=display_name, **overrides)
        project_repository.create(project)
        return project

    return _create_saved_project


@pytest.fixture
def create_consulted_layer() -> Callable[..., ConsultedLayer]:
    def _create_consulted_layer(*, rank: int = 1) -> ConsultedLayer:
        return ConsultedLayer(
            scope=Scope.USER,
            file_path="~/.claude/settings.json",
            exists=True,
            order_rank=rank,
            origin=LayerOrigin.GLOBAL,
            resolves=True,
        )

    return _create_consulted_layer
