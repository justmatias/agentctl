from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

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


def _is_shared_symlink(
    path: Path, inventory_targets: set[Path], shared_directories: list[Path]
) -> bool:
    """Whether `path` is a symlink into the shared inventory or directories."""
    target = path.resolve()
    return path.absolute() != target and (
        target in inventory_targets
        or any(
            target.is_relative_to(directory.resolve())
            for directory in shared_directories
        )
    )


def _annotate_native_layers(
    native_layers: list[PrecedenceLayer],
    inventory_targets: set[Path],
    shared_directories: list[Path],
) -> tuple[list[PrecedenceLayer], set[Path]]:
    """Mark shared symlinks and keep one resolving layer per loaded file.

    Returns the annotated layers and the files they load.
    """
    layers: list[PrecedenceLayer] = []
    loaded_targets: set[Path] = set()
    for layer in native_layers:
        if not isinstance(layer, ConsultedLayer) or not layer.exists:
            layers.append(layer)
            continue
        path = Path(layer.file_path)
        target = path.resolve()
        update: dict[str, object] = {}
        if _is_shared_symlink(path, inventory_targets, shared_directories):
            update["symlink_target"] = str(target)
        if layer.resolves and target in loaded_targets:
            # A higher-precedence layer already loads this file.
            update["resolves"] = False
        elif layer.resolves:
            loaded_targets.add(target)
        layers.append(layer.model_copy(update=update))
    return layers, loaded_targets


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

    def parse(self, path: Path) -> list[Extension]:
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
            path
            for path in (Path(layer.file_path) for layer in shared_layers)
            if any(path.is_relative_to(directory) for directory in shared_directories)
        }
        inventory_targets = {path.resolve() for path in inventory_paths}

        layers, loaded_targets = _annotate_native_layers(
            native.layers, inventory_targets, shared_directories
        )

        native_paths = {Path(layer.file_path).absolute() for layer in native.layers}
        for layer in shared_layers:
            path = Path(layer.file_path)
            if path.absolute() in native_paths:
                continue
            if path in inventory_paths and path.resolve() in loaded_targets:
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
