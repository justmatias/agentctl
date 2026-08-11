"""NullAdapter: a protocol-conformant SourceAdapter that reads and writes nothing.

Exists so the registry, the precedence-chain contract, and capability
declaration can be exercised end-to-end without any real harness
(ROADMAP.md PR 0.4). Not a real adapter — for tests only.
"""

from pathlib import Path

from agentctl.domain import Extension, ExtensionType, PrecedenceChain, Scope, Source

from .protocol import (
    AdapterCapabilities,
    MergeSemantics,
    WalkUpBehavior,
    WalkUpStop,
    WorkflowTargetForm,
)


class NullAdapter:
    """A no-op SourceAdapter: locates nothing, parses nothing, serializes nothing."""

    def __init__(
        self,
        source: Source,
        *,
        extension_types: frozenset[ExtensionType] = frozenset(),
        scopes: frozenset[Scope] = frozenset(),
        workflow_target_forms: frozenset[WorkflowTargetForm] = frozenset(),
    ) -> None:
        self.source = source
        self._capabilities = AdapterCapabilities(
            source=source,
            extension_types=extension_types,
            scopes=scopes,
            workflow_target_forms=workflow_target_forms,
        )

    @staticmethod
    def locate_global_config() -> list[Path]:
        return []

    @staticmethod
    def locate_project_config(_project_root: Path) -> list[Path]:
        return []

    @staticmethod
    def parse(_path: Path) -> list[Extension]:
        return []

    @staticmethod
    def serialize(_extension: Extension) -> str:
        return ""

    @staticmethod
    def walk_up_behavior(_extension_type: ExtensionType) -> WalkUpBehavior:
        return WalkUpBehavior(
            ascends=False,
            stops_at=WalkUpStop.NONE,
            merge_semantics=MergeSemantics.OVERRIDE,
        )

    def precedence_chain(self, _project_root: Path | None) -> PrecedenceChain:
        return PrecedenceChain(source=self.source, project_id=None, layers=[])

    @property
    def capabilities(self) -> AdapterCapabilities:
        return self._capabilities
