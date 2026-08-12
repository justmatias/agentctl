from pathlib import Path

from agentctl.adapters import (
    MergeSemantics,
    SourceAdapter,
    WalkUpStop,
    WorkflowTargetForm,
)
from agentctl.adapters.testing import NullAdapter
from agentctl.domain import ExtensionType, PrecedenceChain, Scope, Source
from tests.polyfactory import ExtensionFactory


def test_isinstance_check_passes() -> None:
    adapter = NullAdapter(Source.CLAUDE_CODE)

    assert isinstance(adapter, SourceAdapter)


def test_locate_global_config_returns_nothing() -> None:
    adapter = NullAdapter(Source.CLAUDE_CODE)

    assert not adapter.locate_global_config()


def test_locate_project_config_returns_nothing() -> None:
    adapter = NullAdapter(Source.CLAUDE_CODE)

    assert not adapter.locate_project_config(Path("/some/project"))


def test_parse_returns_no_extensions() -> None:
    adapter = NullAdapter(Source.CLAUDE_CODE)

    assert not adapter.parse(Path("/some/file.json"))


def test_serialize_returns_empty_string(extension_factory: ExtensionFactory) -> None:
    adapter = NullAdapter(Source.CLAUDE_CODE)

    assert adapter.serialize(extension_factory.build()) == ""


def test_walk_up_behavior_does_not_ascend() -> None:
    adapter = NullAdapter(Source.CLAUDE_CODE)

    behavior = adapter.walk_up_behavior(ExtensionType.MEMORY_FILE)

    assert behavior.ascends is False
    assert behavior.stops_at == WalkUpStop.NONE
    assert behavior.merge_semantics == MergeSemantics.OVERRIDE


def test_precedence_chain_is_empty_and_unscoped_to_a_project() -> None:
    adapter = NullAdapter(Source.CLAUDE_CODE)

    chain = adapter.precedence_chain(Path("/some/project"))

    assert chain == PrecedenceChain(source=Source.CLAUDE_CODE, project_id=None, layers=[])


def test_capabilities_reflects_constructor_arguments() -> None:
    adapter = NullAdapter(
        Source.CURSOR,
        extension_types=frozenset({ExtensionType.MCP_SERVER}),
        scopes=frozenset({Scope.PROJECT, Scope.USER}),
        workflow_target_forms=frozenset({WorkflowTargetForm.SKILL}),
    )

    capabilities = adapter.capabilities

    assert capabilities.source == Source.CURSOR
    assert capabilities.extension_types == frozenset({ExtensionType.MCP_SERVER})
    assert capabilities.scopes == frozenset({Scope.PROJECT, Scope.USER})
    assert capabilities.workflow_target_forms == frozenset({WorkflowTargetForm.SKILL})


def test_capabilities_default_to_empty() -> None:
    adapter = NullAdapter(Source.CLAUDE_CODE)

    capabilities = adapter.capabilities

    assert capabilities.extension_types == frozenset()
    assert capabilities.scopes == frozenset()
    assert capabilities.workflow_target_forms == frozenset()
