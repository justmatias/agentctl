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


@dataclass(kw_only=True)
class CursorAdapter:
    source: ClassVar[Source] = Source.CURSOR
    home: Path = field(default_factory=Path.home)

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            source=self.source,
            extension_types=frozenset({
                ExtensionType.MCP_SERVER,
                ExtensionType.MEMORY_FILE,
                ExtensionType.SKILL,
            }),
            scopes=frozenset({Scope.PROJECT, Scope.USER}),
            workflow_target_forms=frozenset({WorkflowTargetForm.SKILL}),
        )

    @staticmethod
    def _candidate_paths(root: Path, scope: Scope) -> list[Path]:
        cursor_directory = root / ".cursor"
        paths = [
            cursor_directory / "mcp.json",
            *sorted((cursor_directory / "skills").glob("**/*/SKILL.md")),
            *sorted((root / ".agents" / "skills").glob("**/*/SKILL.md")),
        ]
        if scope == Scope.PROJECT:
            paths.extend([
                *sorted((cursor_directory / "rules").rglob("*.mdc")),
                root / "AGENTS.md",
                root / ".cursorrules",
            ])
        return paths

    def locate_global_config(self) -> list[Path]:
        candidates = self._candidate_paths(self.home, Scope.USER)
        return [path for path in candidates if path.is_file()]

    def locate_project_config(self, project_root: Path) -> list[Path]:
        candidates = self._candidate_paths(project_root, Scope.PROJECT)
        return [path for path in candidates if path.is_file()]

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
                Scope.PROJECT,
                LayerOrigin.REGISTERED_PROJECT,
            ))
        locations.append((
            self.home,
            Scope.USER,
            LayerOrigin.GLOBAL,
        ))

        layers: list[PrecedenceLayer] = []
        for rank, (root, scope, origin) in enumerate(locations, start=1):
            layers.extend(
                consulted_file_layer(
                    scope=scope, path=path, origin=origin, order_rank=rank
                )
                for path in self._candidate_paths(root, scope)
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
