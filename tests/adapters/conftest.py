import pytest

from agentctl.adapters import AdapterCapabilities
from agentctl.adapters.fake import NullAdapter
from agentctl.domain import Source


class MismatchedSourceAdapter(NullAdapter):
    """A NullAdapter whose declared capabilities.source disagrees with adapter.source."""

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            source=Source.CURSOR, extension_types=frozenset(), scopes=frozenset()
        )


@pytest.fixture
def mismatched_source_adapter() -> NullAdapter:
    return MismatchedSourceAdapter(Source.CLAUDE_CODE)


@pytest.fixture
def null_adapter() -> NullAdapter:
    return NullAdapter(Source.CLAUDE_CODE)
