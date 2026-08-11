from uuid import uuid4

from agentctl.domain import (
    Conflict,
    ConflictResolution,
    LayerOrigin,
    LayerStatus,
    PrecedenceChain,
    PrecedenceLayer,
    Project,
    Scope,
    Source,
)
from agentctl.storage import Database
from agentctl.storage.sqlite_repositories import (
    SqliteBindingRepository,
    SqliteConflictRepository,
    SqliteExtensionRepository,
    SqlitePrecedenceChainRepository,
    SqliteProjectRepository,
)
from tests.factories import make_binding, make_extension


class TestSqliteExtensionRepository:
    @staticmethod
    def test_create_and_get_round_trip(database: Database) -> None:
        repo = SqliteExtensionRepository(database.connection)
        extension = make_extension()

        repo.create(extension)

        assert repo.get(extension.id) == extension

    @staticmethod
    def test_get_missing_returns_none(database: Database) -> None:
        repo = SqliteExtensionRepository(database.connection)

        assert repo.get(uuid4()) is None

    @staticmethod
    def test_list_returns_all_created(database: Database) -> None:
        repo = SqliteExtensionRepository(database.connection)
        first = make_extension(name="a")
        second = make_extension(name="b")
        repo.create(first)
        repo.create(second)

        assert {e.id for e in repo.list()} == {first.id, second.id}

    @staticmethod
    def test_update_persists_changes(database: Database) -> None:
        repo = SqliteExtensionRepository(database.connection)
        extension = make_extension()
        repo.create(extension)

        renamed = extension.model_copy(update={"name": "renamed"})
        repo.update(renamed)

        assert repo.get(extension.id).name == "renamed"  # type: ignore[union-attr]

    @staticmethod
    def test_delete_removes_row(database: Database) -> None:
        repo = SqliteExtensionRepository(database.connection)
        extension = make_extension()
        repo.create(extension)

        repo.delete(extension.id)

        assert repo.get(extension.id) is None


class TestSqliteBindingRepository:
    @staticmethod
    def test_create_and_get_round_trip(database: Database) -> None:
        extension = make_extension()
        SqliteExtensionRepository(database.connection).create(extension)
        repo = SqliteBindingRepository(database.connection)
        binding = make_binding(extension.id)

        repo.create(binding)

        assert repo.get(binding.id) == binding

    @staticmethod
    def test_list_for_extension_filters(database: Database) -> None:
        extension = make_extension()
        SqliteExtensionRepository(database.connection).create(extension)
        other_extension = make_extension(name="other")
        SqliteExtensionRepository(database.connection).create(other_extension)
        repo = SqliteBindingRepository(database.connection)
        matching = make_binding(extension.id)
        other = make_binding(other_extension.id)
        repo.create(matching)
        repo.create(other)

        result = repo.list_for_extension(extension.id)

        assert [b.id for b in result] == [matching.id]

    @staticmethod
    def test_update_persists_changes(database: Database) -> None:
        extension = make_extension()
        SqliteExtensionRepository(database.connection).create(extension)
        repo = SqliteBindingRepository(database.connection)
        binding = make_binding(extension.id)
        repo.create(binding)

        disabled = binding.model_copy(update={"enabled": False})
        repo.update(disabled)

        assert repo.get(binding.id).enabled is False  # type: ignore[union-attr]

    @staticmethod
    def test_delete_removes_row(database: Database) -> None:
        extension = make_extension()
        SqliteExtensionRepository(database.connection).create(extension)
        repo = SqliteBindingRepository(database.connection)
        binding = make_binding(extension.id)
        repo.create(binding)

        repo.delete(binding.id)

        assert repo.get(binding.id) is None

    @staticmethod
    def test_list_returns_all_bindings(database: Database) -> None:
        extension = make_extension()
        SqliteExtensionRepository(database.connection).create(extension)
        repo = SqliteBindingRepository(database.connection)
        first = make_binding(extension.id)
        second = make_binding(extension.id, file_path=".claude/settings.local.json")
        repo.create(first)
        repo.create(second)

        assert {b.id for b in repo.list()} == {first.id, second.id}


class TestSqliteConflictRepository:
    @staticmethod
    def test_create_and_get_round_trip(database: Database) -> None:
        extension = make_extension()
        SqliteExtensionRepository(database.connection).create(extension)
        binding = make_binding(extension.id)
        SqliteBindingRepository(database.connection).create(binding)
        repo = SqliteConflictRepository(database.connection)
        conflict = Conflict(extension_id=extension.id, binding_ids=[binding.id])

        repo.create(conflict)

        assert repo.get(conflict.id) == conflict

    @staticmethod
    def test_keep_both_intentionally_persists(database: Database) -> None:
        extension = make_extension()
        SqliteExtensionRepository(database.connection).create(extension)
        repo = SqliteConflictRepository(database.connection)
        conflict = Conflict(
            extension_id=extension.id,
            binding_ids=[],
            resolution=ConflictResolution.KEEP_BOTH_INTENTIONALLY,
        )
        repo.create(conflict)

        reloaded = repo.get(conflict.id)

        assert reloaded is not None
        assert reloaded.resolution == ConflictResolution.KEEP_BOTH_INTENTIONALLY

    @staticmethod
    def test_delete_removes_row(database: Database) -> None:
        extension = make_extension()
        SqliteExtensionRepository(database.connection).create(extension)
        repo = SqliteConflictRepository(database.connection)
        conflict = Conflict(extension_id=extension.id, binding_ids=[])
        repo.create(conflict)

        repo.delete(conflict.id)

        assert repo.get(conflict.id) is None

    @staticmethod
    def test_update_persists_resolution(database: Database) -> None:
        extension = make_extension()
        SqliteExtensionRepository(database.connection).create(extension)
        binding = make_binding(extension.id)
        SqliteBindingRepository(database.connection).create(binding)
        repo = SqliteConflictRepository(database.connection)
        conflict = Conflict(extension_id=extension.id, binding_ids=[binding.id])
        repo.create(conflict)

        resolved = conflict.model_copy(
            update={
                "resolution": ConflictResolution.SOURCE_CHOSEN,
                "resolved_binding_id": binding.id,
            }
        )
        repo.update(resolved)

        assert repo.get(conflict.id) == resolved


class TestSqliteProjectRepository:
    @staticmethod
    def test_create_and_get_round_trip(database: Database) -> None:
        repo = SqliteProjectRepository(database.connection)
        project = Project(
            path="/home/user/code/demo",
            display_name="demo",
            detected_sources=[Source.CLAUDE_CODE, Source.DOT_AGENTS],
        )

        repo.create(project)

        assert repo.get(project.id) == project

    @staticmethod
    def test_list_orders_by_registration(database: Database) -> None:
        repo = SqliteProjectRepository(database.connection)
        first = Project(path="/home/user/code/a", display_name="a")
        second = Project(path="/home/user/code/b", display_name="b")
        repo.create(first)
        repo.create(second)

        assert [p.id for p in repo.list()] == [first.id, second.id]

    @staticmethod
    def test_delete_removes_row(database: Database) -> None:
        repo = SqliteProjectRepository(database.connection)
        project = Project(path="/home/user/code/demo", display_name="demo")
        repo.create(project)

        repo.delete(project.id)

        assert repo.get(project.id) is None

    @staticmethod
    def test_update_persists_changes(database: Database) -> None:
        repo = SqliteProjectRepository(database.connection)
        project = Project(path="/home/user/code/demo", display_name="demo")
        repo.create(project)

        renamed = project.model_copy(update={"display_name": "renamed"})
        repo.update(renamed)

        assert repo.get(project.id).display_name == "renamed"  # type: ignore[union-attr]


def _make_layer(*, rank: int = 1) -> PrecedenceLayer:
    return PrecedenceLayer(
        scope=Scope.USER,
        file_path="~/.claude/settings.json",
        exists=True,
        order_rank=rank,
        status=LayerStatus.CONSULTED,
        origin=LayerOrigin.GLOBAL,
        resolves=True,
    )


class TestSqlitePrecedenceChainRepository:
    @staticmethod
    def test_upsert_and_get_global_chain(database: Database) -> None:
        repo = SqlitePrecedenceChainRepository(database.connection)
        chain = PrecedenceChain(source=Source.CLAUDE_CODE, layers=[_make_layer()])

        repo.upsert(chain)

        assert repo.get(Source.CLAUDE_CODE, None) == chain

    @staticmethod
    def test_upsert_and_get_project_chain(database: Database) -> None:
        repo = SqlitePrecedenceChainRepository(database.connection)
        project_id = uuid4()
        chain = PrecedenceChain(
            source=Source.CLAUDE_CODE, project_id=project_id, layers=[_make_layer()]
        )

        repo.upsert(chain)

        assert repo.get(Source.CLAUDE_CODE, project_id) == chain
        assert repo.get(Source.CLAUDE_CODE, None) is None

    @staticmethod
    def test_upsert_replaces_existing_row_for_same_key(database: Database) -> None:
        repo = SqlitePrecedenceChainRepository(database.connection)
        repo.upsert(PrecedenceChain(source=Source.CLAUDE_CODE, layers=[_make_layer(rank=1)]))
        repo.upsert(PrecedenceChain(source=Source.CLAUDE_CODE, layers=[_make_layer(rank=2)]))

        chains = repo.list()

        assert len(chains) == 1
        assert chains[0].layers[0].order_rank == 2

    @staticmethod
    def test_delete_removes_row(database: Database) -> None:
        repo = SqlitePrecedenceChainRepository(database.connection)
        repo.upsert(PrecedenceChain(source=Source.CLAUDE_CODE, layers=[_make_layer()]))

        repo.delete(Source.CLAUDE_CODE, None)

        assert repo.get(Source.CLAUDE_CODE, None) is None
