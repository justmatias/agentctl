"""Polyfactory-based factories for building domain-model instances in tests."""

from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.pytest_plugin import register_fixture

from agentctl.domain import (
    Binding,
    Conflict,
    ConflictResolution,
    Extension,
    McpServerConfig,
)


@register_fixture(name="extension_factory")
class ExtensionFactory(ModelFactory[Extension]):
    __model__ = Extension

    @classmethod
    def canonical_config(cls) -> McpServerConfig:
        return McpServerConfig(command="npx", args=["-y", "github-mcp"])


@register_fixture(name="binding_factory")
class BindingFactory(ModelFactory[Binding]):
    __model__ = Binding


@register_fixture(name="conflict_factory")
class ConflictFactory(ModelFactory[Conflict]):
    __model__ = Conflict

    # Conflict's model_validator requires resolved_binding_id to be set iff
    # resolution is SOURCE_CHOSEN. Fixing both here to a valid combination
    # (rather than letting polyfactory randomize them independently) means
    # build() only fails that check if a caller overrides one without the
    # other, not by chance on every random draw.
    @classmethod
    def resolution(cls) -> ConflictResolution:
        return ConflictResolution.UNRESOLVED

    @classmethod
    def resolved_binding_id(cls) -> None:
        return None
