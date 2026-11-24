import os
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import ClassVar

from jsonyx import TruncatedSyntaxError, loads
from jsonyx.allow import COMMENTS, TRAILING_COMMA
from pydantic import ValidationError

from agentctl.adapters.common import (
    consulted_file_layer,
    parse_memory_file,
    parse_skill,
    project_directories,
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
    McpServerConfig,
    PrecedenceChain,
    PrecedenceLayer,
    Scope,
    Source,
)
from agentctl.utils import logger


def _default_config_directory() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    return (Path(config_home) if config_home else Path.home() / ".config") / "opencode"


@dataclass(kw_only=True)
class OpenCodeAdapter:
    source: ClassVar[Source] = Source.OPENCODE
    config_directory: Path = field(default_factory=_default_config_directory)

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            source=self.source,
            extension_types=frozenset({
                ExtensionType.MCP_SERVER,
                ExtensionType.MEMORY_FILE,
                ExtensionType.SKILL,
            }),
            scopes=frozenset({Scope.USER, Scope.PROJECT}),
            workflow_target_forms=frozenset({WorkflowTargetForm.SKILL}),
        )

    @staticmethod
    def _skill_paths(config_directory: Path) -> list[Path]:
        skills = []
        visited = set()
        for directory, subdirectories, filenames in (config_directory / "skills").walk(
            follow_symlinks=True
        ):
            target = directory.resolve()
            if target in visited:
                subdirectories.clear()
                continue
            visited.add(target)
            subdirectories.sort()
            if "SKILL.md" in filenames:
                skills.append(directory / "SKILL.md")
        return sorted(skills)

    @property
    def _global_candidates(self) -> list[Path]:
        return [
            self.config_directory / "opencode.json",
            self.config_directory / "AGENTS.md",
            *self._skill_paths(self.config_directory),
        ]

    def _project_candidates(self, project_root: Path) -> list[tuple[Path, LayerOrigin]]:
        nearest_first = [
            (
                directory,
                LayerOrigin.ANCESTOR_DIR if index else LayerOrigin.REGISTERED_PROJECT,
            )
            for index, directory in enumerate(
                project_directories(project_root, ascend_outside_git=True)
            )
        ]
        farthest_first = nearest_first[::-1]
        native_configs = [
            (directory / ".opencode" / "opencode.json", origin)
            for directory, origin in farthest_first
        ]
        project_configs = [
            (directory / "opencode.json", origin) for directory, origin in nearest_first
        ]
        instructions = [
            (directory / "AGENTS.md", origin) for directory, origin in nearest_first
        ]
        skills = [
            (path, origin)
            for directory, origin in farthest_first
            for path in self._skill_paths(directory / ".opencode")
        ]
        return native_configs + project_configs + instructions + skills

    def locate_global_config(self) -> list[Path]:
        return [path for path in self._global_candidates if path.is_file()]

    def locate_project_config(self, project_root: Path) -> list[Path]:
        return [
            path for path, _ in self._project_candidates(project_root) if path.is_file()
        ]

    @staticmethod
    def _parse_mcp_entry(name: str, entry: object, path: Path) -> Extension | None:
        if not isinstance(entry, dict):
            logger.warning(f"Skipping malformed OpenCode MCP entry {name!r} in {path}")
            return None
        try:
            match entry.get("type"):
                case "local":
                    command = entry.get("command")
                    if not isinstance(command, list) or not command:
                        logger.warning(
                            f"Skipping OpenCode MCP entry {name!r} without a command in {path}"
                        )
                        return None
                    canonical = McpServerConfig(
                        command=command[0],
                        args=command[1:],
                        env=entry.get("environment", {}),
                    )
                case "remote":
                    canonical = McpServerConfig(
                        url=entry.get("url"), headers=entry.get("headers", {})
                    )
                case _:
                    return None
            return Extension(
                name=name, origin_harness=Source.OPENCODE, canonical_config=canonical
            )
        except ValidationError:
            logger.warning(f"Skipping invalid OpenCode MCP entry {name!r} in {path}")
            return None

    def parse(self, path: Path) -> list[Extension]:
        if not path.is_file():
            return []
        if path.name == "AGENTS.md":
            return parse_memory_file(
                path, source=self.source, is_persistent_memory=False
            )
        if path.name == "SKILL.md":
            return parse_skill(path, source=self.source)
        if path.name != "opencode.json":
            return []
        try:
            data = loads(
                path.read_text(encoding="utf-8"), allow=COMMENTS | TRAILING_COMMA
            )
        except (UnicodeDecodeError, TruncatedSyntaxError):
            logger.warning(f"Skipping malformed OpenCode JSON in {path}")
            return []
        servers = data.get("mcp") if isinstance(data, dict) else None
        if not isinstance(servers, dict):
            return []
        return [
            extension
            for name, entry in servers.items()
            if (extension := self._parse_mcp_entry(name, entry, path)) is not None
        ]

    @staticmethod
    def serialize(_extension: Extension) -> str:
        raise NotImplementedError("OpenCode serialization is not supported")

    @staticmethod
    def walk_up_behavior(extension_type: ExtensionType) -> WalkUpBehavior:
        return WalkUpBehavior(
            True,
            WalkUpStop.GIT_ROOT,
            MergeSemantics.CONCATENATE
            if extension_type == ExtensionType.MEMORY_FILE
            else MergeSemantics.OVERRIDE,
        )

    def precedence_chain(self, project_root: Path | None) -> PrecedenceChain:
        ranks = count(1)
        layers: list[PrecedenceLayer] = []
        if project_root is not None:
            layers.extend(
                consulted_file_layer(
                    scope=Scope.PROJECT,
                    path=path,
                    origin=origin,
                    order_rank=next(ranks),
                )
                for path, origin in self._project_candidates(project_root)
            )
        layers.extend(
            consulted_file_layer(
                scope=Scope.USER,
                path=path,
                origin=LayerOrigin.GLOBAL,
                order_rank=next(ranks),
            )
            for path in self._global_candidates
        )
        return PrecedenceChain(source=self.source, layers=layers)
