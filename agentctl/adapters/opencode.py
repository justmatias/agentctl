import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

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
    Scope,
    Source,
)
from agentctl.utils import logger


def _default_config_directory() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    return (Path(config_home) if config_home else Path.home() / ".config") / "opencode"


def _parse_mcp_servers(path: Path) -> list[Extension]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning(f"Skipping malformed OpenCode JSON in {path}: {exc}")
        return []
    servers = data.get("mcp") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return []
    extensions = []
    for name, entry in servers.items():
        if not isinstance(entry, dict):
            logger.warning(f"Skipping malformed OpenCode MCP entry {name!r} in {path}")
            continue
        try:
            match entry.get("type"):
                case "local":
                    command = entry.get("command")
                    if not isinstance(command, list) or not command:
                        logger.warning(
                            f"Skipping OpenCode MCP entry {name!r} without a command in {path}"
                        )
                        continue
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
                    continue
            extensions.append(
                Extension(
                    name=name,
                    origin_harness=Source.OPENCODE,
                    canonical_config=canonical,
                )
            )
        except ValidationError:
            logger.warning(f"Skipping invalid OpenCode MCP entry {name!r} in {path}")
    return extensions


@dataclass(kw_only=True)
class OpenCodeAdapter:
    source: ClassVar[Source] = Source.OPENCODE
    capabilities: ClassVar[AdapterCapabilities] = AdapterCapabilities(
        source=Source.OPENCODE,
        extension_types=frozenset({
            ExtensionType.MCP_SERVER,
            ExtensionType.MEMORY_FILE,
            ExtensionType.SKILL,
        }),
        scopes=frozenset({Scope.USER, Scope.PROJECT}),
        workflow_target_forms=frozenset({WorkflowTargetForm.SKILL}),
    )
    config_directory: Path = field(default_factory=_default_config_directory)

    def _global_candidates(self) -> list[Path]:
        return [
            self.config_directory / "opencode.json",
            self.config_directory / "AGENTS.md",
            *sorted((self.config_directory / "skills").rglob("SKILL.md")),
        ]

    @staticmethod
    def _project_candidates(project_root: Path) -> list[tuple[Path, LayerOrigin]]:
        directories = [
            (
                directory,
                LayerOrigin.ANCESTOR_DIR if index else LayerOrigin.REGISTERED_PROJECT,
            )
            for index, directory in enumerate(
                project_directories(project_root, ascend_outside_git=True)
            )
        ]
        return [
            *(
                (directory / ".opencode" / "opencode.json", origin)
                for directory, origin in reversed(directories)
            ),
            *(
                (directory / "opencode.json", origin)
                for directory, origin in directories
            ),
            *((directory / "AGENTS.md", origin) for directory, origin in directories),
            *(
                (path, origin)
                for directory, origin in reversed(directories)
                for path in sorted(
                    (directory / ".opencode" / "skills").rglob("SKILL.md")
                )
            ),
        ]

    def locate_global_config(self) -> list[Path]:
        return [path for path in self._global_candidates() if path.is_file()]

    def locate_project_config(self, project_root: Path) -> list[Path]:
        return [
            path for path, _ in self._project_candidates(project_root) if path.is_file()
        ]

    def parse(self, path: Path) -> list[Extension]:
        if not path.is_file():
            return []
        match path.name:
            case "opencode.json":
                return _parse_mcp_servers(path)
            case "AGENTS.md":
                return parse_memory_file(
                    path, source=self.source, is_persistent_memory=False
                )
            case "SKILL.md":
                return parse_skill(path, source=self.source)
            case _:
                return []

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
        candidates = []
        if project_root is not None:
            candidates.extend(
                (path, Scope.PROJECT, origin)
                for path, origin in self._project_candidates(project_root)
            )
        candidates.extend(
            (path, Scope.USER, LayerOrigin.GLOBAL) for path in self._global_candidates()
        )
        return PrecedenceChain(
            source=self.source,
            layers=[
                consulted_file_layer(
                    scope=scope, path=path, origin=origin, order_rank=rank
                )
                for rank, (path, scope, origin) in enumerate(candidates, start=1)
            ],
        )
