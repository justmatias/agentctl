from pathlib import Path

from agentctl.adapters import (
    MergeSemantics,
    SourceAdapter,
    WalkUpStop,
    WorkflowTargetForm,
)
from agentctl.adapters.fake import NullAdapter
from agentctl.domain import ExtensionType, PrecedenceChain, Scope, Source
from tests.polyfactory import ExtensionFactory


def test_isinstance_check_passes(null_adapter: NullAdapter) -> None:
    assert isinstance(null_adapter, SourceAdapter)


def test_no_op_methods_report_empty_results(
    null_adapter: NullAdapter, extension_factory: ExtensionFactory
) -> None:
    assert not null_adapter.locate_global_config()
    assert not null_adapter.locate_project_config(Path("/some/project"))
    assert not null_adapter.parse(Path("/some/file.json"))
    assert null_adapter.serialize(extension_factory.build()) == ""

    behavior = null_adapter.walk_up_behavior(ExtensionType.MEMORY_FILE)
    assert behavior.ascends is False
    assert behavior.stops_at == WalkUpStop.NONE
    assert behavior.merge_semantics == MergeSemantics.OVERRIDE

    chain = null_adapter.precedence_chain(Path("/some/project"))
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
