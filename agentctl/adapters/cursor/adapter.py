from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from agentctl.adapters.common import (
    consulted_file_layer,
    parse_mcp_servers_json,
    parse_memory_file,
    parse_skill,
)
from agentctl.adapters.protocol import (
    AdapterCapabilities,
    MergeSemantics,
    WalkUpBehavior,
    WalkUpStop,
    WorkflowTargetForm,
)
from agentctl.domain import (
    Extension,
    ExtensionType,
    LayerOrigin,
    NotConsultedLayer,
    PrecedenceChain,
    PrecedenceLayer,
    Scope,
    Source,
    UnconfirmedLayer,
)


def _configuration_paths(root: Path) -> list[Path]:
    return [
        root / ".cursor" / "mcp.json",
        *sorted((root / ".cursor" / "skills").glob("**/*/SKILL.md")),
        *sorted((root / ".agents" / "skills").glob("**/*/SKILL.md")),
    ]


def _project_paths(project_root: Path) -> list[Path]:
    return [
        *_configuration_paths(project_root),
        *sorted((project_root / ".cursor" / "rules").rglob("*.mdc")),
        project_root / "AGENTS.md",
        project_root / ".cursorrules",
    ]


@dataclass(kw_only=True)
class CursorAdapter:
    source: ClassVar[Source] = Source.CURSOR
    capabilities: ClassVar[AdapterCapabilities] = AdapterCapabilities(
        source=Source.CURSOR,
        extension_types=frozenset({
            ExtensionType.MCP_SERVER,
            ExtensionType.MEMORY_FILE,
            ExtensionType.SKILL,
        }),
        scopes=frozenset({Scope.PROJECT, Scope.USER}),
        workflow_target_forms=frozenset({WorkflowTargetForm.SKILL}),
    )
    home: Path = field(default_factory=Path.home)

    def locate_global_config(self) -> list[Path]:
        return [path for path in _configuration_paths(self.home) if path.is_file()]

    @staticmethod
    def locate_project_config(project_root: Path) -> list[Path]:
        return [path for path in _project_paths(project_root) if path.is_file()]

    def parse(self, path: Path) -> list[Extension]:
        if not path.is_file():
            return []
        if path.name == "mcp.json":
            return parse_mcp_servers_json(path, source=self.source)
        if path.name == "SKILL.md":
            return parse_skill(path, source=self.source)
        if path.name in {"AGENTS.md", ".cursorrules"} or path.suffix == ".mdc":
            return parse_memory_file(
                path, source=self.source, is_persistent_memory=False
            )
        return []

    @staticmethod
    def serialize(_extension: Extension) -> str:
        raise NotImplementedError("Cursor serialization is not supported")

    @staticmethod
    def walk_up_behavior(extension_type: ExtensionType) -> WalkUpBehavior:
        return WalkUpBehavior(
            ascends=False,
            stops_at=WalkUpStop.NONE,
            merge_semantics=(
                MergeSemantics.CONCATENATE
                if extension_type == ExtensionType.MEMORY_FILE
                else MergeSemantics.OVERRIDE
            ),
        )

    def precedence_chain(self, project_root: Path | None) -> PrecedenceChain:
        locations = []
        if project_root is not None:
            locations.append((
                project_root,
                _project_paths(project_root),
                Scope.PROJECT,
                LayerOrigin.REGISTERED_PROJECT,
            ))
        locations.append((
            self.home,
            _configuration_paths(self.home),
            Scope.USER,
            LayerOrigin.GLOBAL,
        ))

        layers: list[PrecedenceLayer] = []
        for rank, (root, paths, scope, origin) in enumerate(locations, start=1):
            layers.extend(
                consulted_file_layer(
                    scope=scope, path=path, origin=origin, order_rank=rank
                )
                for path in paths
            )
            # Cursor documents nested AGENTS.md for files in that subtree, but
            # does not document a shared .agents/AGENTS.md loaded project-wide.
            shared_instructions = root / ".agents" / "AGENTS.md"
            if shared_instructions.is_file() and not (
                scope == Scope.PROJECT
                and (root / "AGENTS.md").resolve() == shared_instructions.resolve()
            ):
                layer_type = (
                    UnconfirmedLayer if scope == Scope.PROJECT else NotConsultedLayer
                )
                layers.append(
                    layer_type(
                        scope=scope,
                        file_path=str(shared_instructions),
                        exists=True,
                        origin=origin,
                    )
                )
        return PrecedenceChain(source=self.source, layers=layers)
