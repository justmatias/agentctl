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
    def locate_project_config(project_root: Path) -> list[Path]:
        del project_root
        return []

    @staticmethod
    def parse(path: Path) -> list[Extension]:
        del path
        return []

    @staticmethod
    def serialize(extension: Extension) -> str:
        del extension
        return ""

    @staticmethod
    def walk_up_behavior(extension_type: ExtensionType) -> WalkUpBehavior:
        del extension_type
        return WalkUpBehavior(
            ascends=False, stops_at=WalkUpStop.NONE, merge_semantics=MergeSemantics.OVERRIDE
        )

    def precedence_chain(self, project_root: Path | None) -> PrecedenceChain:
        del project_root
        return PrecedenceChain(source=self.source, project_id=None, layers=[])

    @property
    def capabilities(self) -> AdapterCapabilities:
        return self._capabilities
