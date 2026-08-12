"""Polyfactory-based factories for building domain-model instances in tests."""

from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.pytest_plugin import register_fixture

from agentctl.domain import Binding, Extension, McpServerConfig


@register_fixture
class ExtensionFactory(ModelFactory[Extension]):
    __model__ = Extension

    @classmethod
    def canonical_config(cls) -> McpServerConfig:
        return McpServerConfig(command="npx", args=["-y", "github-mcp"])


@register_fixture
class BindingFactory(ModelFactory[Binding]):
    __model__ = Binding
