from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from agentctl.adapters.common import parse_memory_file, serialize_memory_file
from agentctl.adapters.protocol import (
    AdapterCapabilities,
    MergeSemantics,
    SourceAdapter,
    WalkUpBehavior,
    WalkUpStop,
)
from agentctl.domain import (
    ConsultedLayer,
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


class AnnotatedNativeLayers(BaseModel):
    layers: list[PrecedenceLayer]
    loaded_targets: set[Path]


@dataclass(kw_only=True)
class DotAgentsAdapter:
    source: ClassVar[Source] = Source.DOT_AGENTS
    capabilities: ClassVar[AdapterCapabilities] = AdapterCapabilities(
        source=Source.DOT_AGENTS,
        extension_types=frozenset({ExtensionType.MEMORY_FILE}),
        scopes=frozenset({Scope.GLOBAL, Scope.PROJECT}),
    )
    home: Path = field(default_factory=Path.home)

    @staticmethod
    def _locate_config(root: Path, *, project: bool) -> list[Path]:
        shared = root / ".agents"
        candidates = [shared / "AGENTS.md", shared / "memory" / "MEMORY.md"]
        if project:
            candidates.extend([root / "AGENTS.md", root / "MEMORY.md"])
        paths = [shared] if shared.is_dir() else []
        return paths + [path for path in candidates if path.is_file()]

    def locate_global_config(self) -> list[Path]:
        return self._locate_config(self.home, project=False)

    @classmethod
    def locate_project_config(cls, project_root: Path) -> list[Path]:
        return cls._locate_config(project_root, project=True)

    def parse(self, path: Path, *, scope: Scope | None = None) -> list[Extension]:
        del scope
        if path.name not in {"AGENTS.md", "MEMORY.md"} or not path.is_file():
            return []
        return parse_memory_file(
            path, source=self.source, is_persistent_memory=path.name == "MEMORY.md"
        )

    @staticmethod
    def serialize(extension: Extension) -> str:
        return serialize_memory_file(extension)

    @staticmethod
    def walk_up_behavior(_extension_type: ExtensionType) -> WalkUpBehavior:
        return WalkUpBehavior(False, WalkUpStop.NONE, MergeSemantics.OVERRIDE)

    def precedence_chain(self, project_root: Path | None) -> PrecedenceChain:
        layers: list[PrecedenceLayer] = [
            UnconfirmedLayer(
                file_path=str(path),
                exists=True,
                scope=Scope.GLOBAL,
                origin=LayerOrigin.GLOBAL,
            )
            for path in self.locate_global_config()
            if path.is_file()
        ]
        if project_root is not None:
            layers.extend(
                UnconfirmedLayer(
                    file_path=str(path),
                    exists=True,
                    scope=Scope.PROJECT,
                    origin=LayerOrigin.REGISTERED_PROJECT,
                )
                for path in self.locate_project_config(project_root)
                if path.is_file()
            )
        return PrecedenceChain(source=self.source, layers=layers)

    @staticmethod
    def _annotate_native_layers(
        native_layers: list[PrecedenceLayer],
        inventory_targets: set[Path],
        shared_roots: list[Path],
    ) -> AnnotatedNativeLayers:
        layers: list[PrecedenceLayer] = []
        loaded_targets: set[Path] = set()
        for layer in native_layers:
            if not isinstance(layer, ConsultedLayer) or not layer.exists:
                layers.append(layer)
                continue
            path = Path(layer.file_path)
            target = path.resolve()
            updates: dict[str, str | bool] = {}
            if path.absolute() != target and (
                target in inventory_targets
                or any(target.is_relative_to(root) for root in shared_roots)
            ):
                updates["symlink_target"] = str(target)
            if layer.resolves:
                if target in loaded_targets:
                    updates["resolves"] = False
                loaded_targets.add(target)
            layers.append(layer.model_copy(update=updates) if updates else layer)
        return AnnotatedNativeLayers(layers=layers, loaded_targets=loaded_targets)

    def consumption_report(
        self, harness: SourceAdapter, project_root: Path | None
    ) -> PrecedenceChain:
        """Annotate the harness's own chain with discovered shared files."""
        native = harness.precedence_chain(project_root)
        shared_directories = [self.home / ".agents"]
        if project_root is not None:
            shared_directories.append(project_root / ".agents")
        shared_layers = self.precedence_chain(project_root).layers
        inventory_paths = {
            path: path.resolve()
            for path in (Path(layer.file_path) for layer in shared_layers)
            if any(path.is_relative_to(directory) for directory in shared_directories)
        }
        annotated = self._annotate_native_layers(
            native.layers,
            set(inventory_paths.values()),
            [directory.resolve() for directory in shared_directories],
        )

        layers = annotated.layers
        native_paths = {Path(layer.file_path).absolute() for layer in native.layers}
        for layer in shared_layers:
            path = Path(layer.file_path)
            if path.absolute() in native_paths:
                continue
            if inventory_paths.get(path) in annotated.loaded_targets:
                continue
            # Claude's native instruction discovery excludes .agents directories.
            # https://code.claude.com/docs/en/memory#when-claude-code-reads-agents-md
            if native.source == Source.CLAUDE_CODE and path.parent.name == ".agents":
                layers.append(
                    NotConsultedLayer(
                        scope=layer.scope,
                        file_path=layer.file_path,
                        exists=layer.exists,
                        origin=layer.origin,
                    )
                )
            else:
                layers.append(layer)
        return native.model_copy(update={"layers": layers})
