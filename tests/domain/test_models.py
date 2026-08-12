import pytest
from pydantic import ValidationError

from agentctl.domain import (
    Binding,
    Conflict,
    ConflictResolution,
    Extension,
    ExtensionType,
    LayerOrigin,
    LayerStatus,
    McpServerConfig,
    MemoryFileConfig,
    PrecedenceChain,
    PrecedenceLayer,
    Project,
    Scope,
    SkillConfig,
    Source,
    SyncState,
)
from tests.domain.conftest import assert_round_trips
from tests.factories import make_extension


class TestExtensionRoundTrip:
    @staticmethod
    @pytest.mark.parametrize(
        ("type_", "config"),
        [
            (
                ExtensionType.MCP_SERVER,
                McpServerConfig(command="npx", args=["-y", "github-mcp"]),
            ),
            (
                ExtensionType.MEMORY_FILE,
                MemoryFileConfig(content="# Notes", is_persistent_memory=True),
            ),
            (
                ExtensionType.SKILL,
                SkillConfig(description="Does a thing", body="# Skill"),
            ),
        ],
    )
    def test_round_trips_through_json(type_: ExtensionType, config: object) -> None:
        extension = make_extension(type=type_, canonical_config=config)

        assert_round_trips(extension)


class TestExtensionValidation:
    @staticmethod
    def test_raises_when_canonical_config_does_not_match_type() -> None:
        with pytest.raises(ValidationError):
            make_extension(
                type=ExtensionType.SKILL,
                canonical_config=McpServerConfig(command="npx"),
            )

    @staticmethod
    def test_mcp_server_config_requires_command_or_url() -> None:
        with pytest.raises(ValidationError):
            McpServerConfig()


class TestBinding:
    @staticmethod
    def test_round_trips_through_json(extension: Extension) -> None:
        binding = Binding(
            extension_id=extension.id,
            harness=Source.CLAUDE_CODE,
            scope=Scope.PROJECT,
            file_path=".claude/settings.json",
            sync_state=SyncState.DRIFTED,
        )

        assert_round_trips(binding)


class TestConflict:
    @staticmethod
    def test_source_chosen_requires_resolved_binding_id(extension: Extension) -> None:
        with pytest.raises(ValidationError):
            Conflict(
                extension_id=extension.id,
                binding_ids=[],
                resolution=ConflictResolution.SOURCE_CHOSEN,
            )

    @staticmethod
    def test_unresolved_forbids_resolved_binding_id(extension: Extension) -> None:
        binding = Binding(
            extension_id=extension.id,
            harness=Source.CLAUDE_CODE,
            scope=Scope.USER,
            file_path="~/.claude/settings.json",
        )
        with pytest.raises(ValidationError):
            Conflict(
                extension_id=extension.id,
                binding_ids=[binding.id],
                resolved_binding_id=binding.id,
                resolution=ConflictResolution.UNRESOLVED,
            )

    @staticmethod
    def test_keep_both_intentionally_round_trips(extension: Extension) -> None:
        conflict = Conflict(
            extension_id=extension.id,
            binding_ids=[],
            resolution=ConflictResolution.KEEP_BOTH_INTENTIONALLY,
        )

        assert_round_trips(conflict)


class TestProject:
    @staticmethod
    def test_rejects_relative_path() -> None:
        with pytest.raises(ValidationError):
            Project(path="relative/path", display_name="demo")

    @staticmethod
    def test_round_trips_through_json() -> None:
        project = Project(path="/home/user/code/demo", display_name="demo")

        assert_round_trips(project)


class TestPrecedenceChain:
    @staticmethod
    def test_consulted_layer_requires_order_rank() -> None:
        with pytest.raises(ValidationError):
            PrecedenceLayer(
                scope=Scope.PROJECT,
                file_path=".claude/settings.json",
                exists=True,
                status=LayerStatus.CONSULTED,
                origin=LayerOrigin.REGISTERED_PROJECT,
                resolves=True,
            )

    @staticmethod
    def test_unconfirmed_layer_forbids_order_rank() -> None:
        with pytest.raises(ValidationError):
            PrecedenceLayer(
                scope=Scope.PROJECT,
                file_path=".agents/AGENTS.md",
                exists=True,
                order_rank=1,
                status=LayerStatus.UNCONFIRMED,
                origin=LayerOrigin.REGISTERED_PROJECT,
                resolves=False,
            )

    @staticmethod
    def test_unconfirmed_layer_forbids_resolves() -> None:
        with pytest.raises(ValidationError):
            PrecedenceLayer(
                scope=Scope.PROJECT,
                file_path=".agents/AGENTS.md",
                exists=True,
                status=LayerStatus.UNCONFIRMED,
                origin=LayerOrigin.REGISTERED_PROJECT,
                resolves=True,
            )

    @staticmethod
    def test_unconfirmed_layer_does_not_change_winner() -> None:
        """A fixture whose top layer is unconfirmed resolves to the same
        winner as one where that layer is absent"""
        confirmed_layer = PrecedenceLayer(
            scope=Scope.USER,
            file_path="~/.claude/settings.json",
            exists=True,
            order_rank=1,
            status=LayerStatus.CONSULTED,
            origin=LayerOrigin.GLOBAL,
            resolves=True,
        )
        unconfirmed_layer = PrecedenceLayer(
            scope=Scope.PROJECT,
            file_path=".agents/AGENTS.md",
            exists=True,
            status=LayerStatus.UNCONFIRMED,
            origin=LayerOrigin.REGISTERED_PROJECT,
            resolves=False,
        )

        with_unconfirmed = PrecedenceChain(
            source=Source.CLAUDE_CODE, layers=[unconfirmed_layer, confirmed_layer]
        )
        without_unconfirmed = PrecedenceChain(
            source=Source.CLAUDE_CODE, layers=[confirmed_layer]
        )

        def winner(chain: PrecedenceChain) -> PrecedenceLayer:
            return next(layer for layer in chain.layers if layer.resolves)

        assert winner(with_unconfirmed) == winner(without_unconfirmed)

    @staticmethod
    def test_round_trips_through_json() -> None:
        layer = PrecedenceLayer(
            scope=Scope.USER,
            file_path="~/.claude/settings.json",
            exists=True,
            order_rank=1,
            status=LayerStatus.CONSULTED,
            origin=LayerOrigin.GLOBAL,
            resolves=True,
        )
        chain = PrecedenceChain(source=Source.CLAUDE_CODE, layers=[layer])

        assert_round_trips(chain)
