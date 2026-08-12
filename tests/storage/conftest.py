from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from agentctl.domain import (
    Binding,
    Conflict,
    ConsultedLayer,
    Extension,
    LayerOrigin,
    PrecedenceChain,
    Project,
    Scope,
    Source,
)
from agentctl.storage import (
    Database,
    SqliteBindingRepository,
    SqliteConflictRepository,
    SqliteExtensionRepository,
    SqlitePrecedenceChainRepository,
    SqliteProjectRepository,
)
from tests.factories import BindingFactory, ConflictFactory, ExtensionFactory


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
def other_extension(create_saved_extension: Callable[..., Extension]) -> Extension:
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
def other_binding(
    create_saved_binding: Callable[..., Binding], other_extension: Extension
) -> Binding:
    return create_saved_binding(extension_id=other_extension.id)


@pytest.fixture
def create_saved_conflict(
    conflict_repository: SqliteConflictRepository,
    conflict_factory: ConflictFactory,
) -> Callable[..., Conflict]:
    def _create_saved_conflict(
        *, extension_id: UUID, binding_ids: list[UUID], **overrides: Any
    ) -> Conflict:
        conflict = conflict_factory.build(
            extension_id=extension_id, binding_ids=binding_ids, **overrides
        )
        conflict_repository.create(conflict)
        return conflict

    return _create_saved_conflict


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
def create_saved_precedence_chain(
    precedence_chain_repository: SqlitePrecedenceChainRepository,
) -> Callable[..., PrecedenceChain]:
    # No polyfactory factory: source/project_id/layers are exactly the
    # fields every test varies deliberately (global vs. project scope,
    # specific layer content), so randomizing them would fight the tests
    # rather than remove noise from them — same reasoning as Project.
    def _create_saved_precedence_chain(
        *, source: Source = Source.CLAUDE_CODE, **overrides: Any
    ) -> PrecedenceChain:
        chain = PrecedenceChain(source=source, **overrides)
        precedence_chain_repository.upsert(chain)
        return chain

    return _create_saved_precedence_chain


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


@pytest.fixture
def consulted_layer(
    create_consulted_layer: Callable[..., ConsultedLayer],
) -> ConsultedLayer:
    return create_consulted_layer()
