from pathlib import Path

import pytest

from agentctl.adapters import AdapterRegistry
from agentctl.adapters.fake import NullAdapter
from agentctl.domain import ExtensionType, Scope, Source


def test_register_rejects_an_adapter_that_does_not_implement_the_protocol() -> None:
    registry = AdapterRegistry()

    with pytest.raises(TypeError, match="does not implement the SourceAdapter protocol"):
        registry.register(object())  # type: ignore[arg-type]


def test_register_rejects_mismatched_source_and_capabilities_source(
    mismatched_source_adapter: NullAdapter,
) -> None:
    registry = AdapterRegistry()

    with pytest.raises(ValueError, match="does not match"):
        registry.register(mismatched_source_adapter)


def test_get_returns_none_when_nothing_registered() -> None:
    registry = AdapterRegistry()

    assert registry.get(Source.CLAUDE_CODE) is None


def test_register_then_get_returns_the_same_adapter() -> None:
    registry = AdapterRegistry()
    adapter = NullAdapter(Source.CLAUDE_CODE)

    registry.register(adapter)

    assert registry.get(Source.CLAUDE_CODE) is adapter


def test_register_replaces_an_existing_adapter_for_the_same_source() -> None:
    registry = AdapterRegistry()
    first = NullAdapter(Source.CLAUDE_CODE)
    second = NullAdapter(Source.CLAUDE_CODE)

    registry.register(first)
    registry.register(second)

    assert registry.get(Source.CLAUDE_CODE) is second


def test_list_returns_every_registered_adapter() -> None:
    registry = AdapterRegistry()
    claude = NullAdapter(Source.CLAUDE_CODE)
    cursor = NullAdapter(Source.CURSOR)

    registry.register(claude)
    registry.register(cursor)

    assert set(registry.list()) == {claude, cursor}


def test_unregister_removes_the_adapter() -> None:
    registry = AdapterRegistry()
    registry.register(NullAdapter(Source.CLAUDE_CODE))

    registry.unregister(Source.CLAUDE_CODE)

    assert registry.get(Source.CLAUDE_CODE) is None


def test_unregister_missing_source_is_a_noop() -> None:
    registry = AdapterRegistry()

    registry.unregister(Source.CLAUDE_CODE)

    assert not registry.list()


def test_full_round_trip_through_the_registry() -> None:
    """ROADMAP.md PR 0.4 done-when: a fake adapter is registered and exercised
    end-to-end through the registry — no real harness anywhere in this PR."""
    registry = AdapterRegistry()
    fake = NullAdapter(
        Source.DOT_AGENTS,
        extension_types=frozenset({ExtensionType.MEMORY_FILE}),
        scopes=frozenset({Scope.PROJECT, Scope.GLOBAL}),
    )
    registry.register(fake)

    adapter = registry.get(Source.DOT_AGENTS)

    assert adapter is not None
    assert adapter.locate_global_config() == []
    assert adapter.locate_project_config(Path("/some/project")) == []
    assert adapter.capabilities.extension_types == frozenset({ExtensionType.MEMORY_FILE})
    chain = adapter.precedence_chain(None)
    assert chain.source == Source.DOT_AGENTS
    assert chain.layers == []
