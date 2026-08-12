from typing import cast

import pytest
from pydantic import ValidationError

from agentctl.domain import (
    Conflict,
    ConflictResolution,
    ConsultedLayer,
    ExtensionType,
    LayerOrigin,
    McpServerConfig,
    MemoryFileConfig,
    NotConsultedLayer,
    PrecedenceChain,
    Project,
    Scope,
    SkillConfig,
    Source,
    SyncState,
    UnconfirmedLayer,
)
from tests.domain.conftest import assert_round_trips
from tests.factories import BindingFactory, ExtensionFactory


@pytest.fixture(
    params=[
        McpServerConfig(command="npx", args=["-y", "github-mcp"]),
        MemoryFileConfig(content="# Notes", is_persistent_memory=True),
        SkillConfig(description="Does a thing", body="# Skill"),
    ]
)
def canonical_config(
    request: pytest.FixtureRequest,
) -> McpServerConfig | MemoryFileConfig | SkillConfig:
    return cast(McpServerConfig | MemoryFileConfig | SkillConfig, request.param)


def test_extension_round_trips_through_json(
    extension_factory: ExtensionFactory,
    canonical_config: McpServerConfig | MemoryFileConfig | SkillConfig,
) -> None:
    extension = extension_factory.build(canonical_config=canonical_config)

    assert_round_trips(extension)


def test_extension_type_is_derived_from_canonical_config(
    extension_factory: ExtensionFactory,
) -> None:
    extension = extension_factory.build(
        canonical_config=SkillConfig(description="Does a thing", body="# Skill")
    )

    assert extension.type == ExtensionType.SKILL


def test_canonical_config_rejects_mismatched_type_literal() -> None:
    with pytest.raises(ValidationError):
        McpServerConfig(type=ExtensionType.SKILL, command="npx")


def test_mcp_server_config_requires_command_or_url() -> None:
    with pytest.raises(ValidationError):
        McpServerConfig()


def test_binding_round_trips_through_json(
    extension_factory: ExtensionFactory, binding_factory: BindingFactory
) -> None:
    extension = extension_factory.build()
    binding = binding_factory.build(
        extension_id=extension.id, sync_state=SyncState.DRIFTED
    )

    assert_round_trips(binding)


def test_conflict_source_chosen_requires_resolved_binding_id(
    extension_factory: ExtensionFactory,
) -> None:
    extension = extension_factory.build()
    with pytest.raises(ValidationError):
        Conflict(
            extension_id=extension.id,
            binding_ids=[],
            resolution=ConflictResolution.SOURCE_CHOSEN,
        )


def test_conflict_unresolved_forbids_resolved_binding_id(
    extension_factory: ExtensionFactory, binding_factory: BindingFactory
) -> None:
    extension = extension_factory.build()
    binding = binding_factory.build(extension_id=extension.id)
    with pytest.raises(ValidationError):
        Conflict(
            extension_id=extension.id,
            binding_ids=[binding.id],
            resolved_binding_id=binding.id,
            resolution=ConflictResolution.UNRESOLVED,
        )


def test_conflict_keep_both_intentionally_round_trips(
    extension_factory: ExtensionFactory,
) -> None:
    extension = extension_factory.build()
    conflict = Conflict(
        extension_id=extension.id,
        binding_ids=[],
        resolution=ConflictResolution.KEEP_BOTH_INTENTIONALLY,
    )

    assert_round_trips(conflict)


def test_project_rejects_relative_path() -> None:
    with pytest.raises(ValidationError):
        Project(path="relative/path", display_name="demo")


def test_project_round_trips_through_json() -> None:
    project = Project(path="/home/user/code/demo", display_name="demo")

    assert_round_trips(project)


def test_consulted_layer_requires_order_rank() -> None:
    with pytest.raises(ValidationError):
        ConsultedLayer.model_validate(
            {
                "scope": Scope.PROJECT,
                "file_path": ".claude/settings.json",
                "exists": True,
                "origin": LayerOrigin.REGISTERED_PROJECT,
                "resolves": True,
            }
        )


def test_unconfirmed_layer_forbids_order_rank() -> None:
    with pytest.raises(ValidationError):
        UnconfirmedLayer.model_validate(
            {
                "scope": Scope.PROJECT,
                "file_path": ".agents/AGENTS.md",
                "exists": True,
                "order_rank": 1,
                "origin": LayerOrigin.REGISTERED_PROJECT,
                "resolves": False,
            }
        )


def test_unconfirmed_layer_forbids_resolves() -> None:
    with pytest.raises(ValidationError):
        UnconfirmedLayer(
            scope=Scope.PROJECT,
            file_path=".agents/AGENTS.md",
            exists=True,
            origin=LayerOrigin.REGISTERED_PROJECT,
            resolves=True,
        )


def test_unconfirmed_layer_does_not_change_winner() -> None:
    """A fixture whose top layer is unconfirmed resolves to the same
    winner as one where that layer is absent"""
    confirmed_layer = ConsultedLayer(
        scope=Scope.USER,
        file_path="~/.claude/settings.json",
        exists=True,
        order_rank=1,
        origin=LayerOrigin.GLOBAL,
        resolves=True,
    )
    unconfirmed_layer = UnconfirmedLayer(
        scope=Scope.PROJECT,
        file_path=".agents/AGENTS.md",
        exists=True,
        origin=LayerOrigin.REGISTERED_PROJECT,
        resolves=False,
    )

    with_unconfirmed = PrecedenceChain(
        source=Source.CLAUDE_CODE, layers=[unconfirmed_layer, confirmed_layer]
    )
    without_unconfirmed = PrecedenceChain(
        source=Source.CLAUDE_CODE, layers=[confirmed_layer]
    )

    def winner(
        chain: PrecedenceChain,
    ) -> ConsultedLayer | NotConsultedLayer | UnconfirmedLayer:
        return next(layer for layer in chain.layers if layer.resolves)

    assert winner(with_unconfirmed) == winner(without_unconfirmed)


def test_precedence_chain_round_trips_through_json() -> None:
    layer = ConsultedLayer(
        scope=Scope.USER,
        file_path="~/.claude/settings.json",
        exists=True,
        order_rank=1,
        origin=LayerOrigin.GLOBAL,
        resolves=True,
    )
    chain = PrecedenceChain(source=Source.CLAUDE_CODE, layers=[layer])

    assert_round_trips(chain)
