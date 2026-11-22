import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import ClassVar

from agentctl.adapters.common import (
    consulted_file_layer,
    dispatch_serializer,
    parse_mcp_servers_toml,
    parse_memory_file,
    platform_specific_path,
)
from agentctl.adapters.protocol import (
    AdapterCapabilities,
    MergeSemantics,
    WalkUpBehavior,
    WalkUpStop,
    WorkflowTargetForm,
)
from agentctl.domain import (
    ConsultedLayer,
    Extension,
    ExtensionType,
    LayerOrigin,
    PrecedenceChain,
    PrecedenceLayer,
    Scope,
    Source,
)
from agentctl.utils import logger

from .serializers import SERIALIZERS

CODEX_HOME_VARIABLE = "CODEX_HOME"
SYSTEM_CONFIG_DIRECTORY = Path("/etc/codex")
CONFIG_FILENAME = "config.toml"
MANAGED_CONFIG_FILENAME = "managed_config.toml"
INSTRUCTIONS_FILENAME = "AGENTS.md"
INSTRUCTIONS_OVERRIDE_FILENAME = "AGENTS.override.md"
COMMAND_LINE_ARGUMENTS = "(command-line arguments)"


def default_codex_home() -> Path:
    """Codex's home directory: `~/.codex` unless `CODEX_HOME` overrides it."""
    override = os.environ.get(CODEX_HOME_VARIABLE)
    return Path(override) if override else Path.home() / ".codex"


def _project_directories(working_directory: Path) -> tuple[Path, ...]:
    directory = working_directory.resolve()
    directories = (directory, *directory.parents)
    for index, candidate in enumerate(directories):
        git_marker = candidate / ".git"
        if git_marker.is_file() or (git_marker / "HEAD").is_file():
            return directories[: index + 1]
    return (working_directory,)


@dataclass(kw_only=True)
class CodexCliAdapter:
    """Reads Codex CLI's on-disk config into canonical `Extension` records"""

    source: ClassVar[Source] = Source.CODEX_CLI
    codex_home: Path = field(default_factory=default_codex_home)
    # Codex reads machine-wide config from /etc/codex on Unix only; on Windows
    # the layer simply never exists, so the Unix path is still what we report.
    system_config_directory: Path = SYSTEM_CONFIG_DIRECTORY

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            source=Source.CODEX_CLI,
            extension_types=frozenset({
                ExtensionType.MCP_SERVER,
                ExtensionType.MEMORY_FILE,
            }),
            # Codex has no gitignored per-project layer of its own, so nothing
            # maps to Scope.LOCAL.
            scopes=frozenset({
                Scope.MANAGED,
                Scope.PROJECT,
                Scope.USER,
                Scope.GLOBAL,
            }),
            # Codex scans `.agents/skills` (developers.openai.com/codex/skills,
            # fetched 2026-08-14), so a workflow can compile down to a skill for
            # it — but those files belong to the shared `.agents` source, which
            # is its own adapter, not to this one.
            workflow_target_forms=frozenset({WorkflowTargetForm.SKILL}),
        )

    @property
    def user_config_path(self) -> Path:
        return self.codex_home / CONFIG_FILENAME

    @property
    def system_config_path(self) -> Path:
        return self.system_config_directory / CONFIG_FILENAME

    @property
    def managed_config_path(self) -> Path:
        """Where an administrator's managed config lives on this platform."""
        return platform_specific_path(
            darwin=self.system_config_directory / MANAGED_CONFIG_FILENAME,
            windows=self.codex_home / MANAGED_CONFIG_FILENAME,
            default=self.system_config_directory / MANAGED_CONFIG_FILENAME,
        )

    @staticmethod
    def project_config_path(project_root: Path) -> Path:
        return project_root / ".codex" / CONFIG_FILENAME

    def locate_global_config(self) -> list[Path]:
        candidates = [
            self.managed_config_path,
            self.system_config_path,
            self.user_config_path,
            self.codex_home / INSTRUCTIONS_OVERRIDE_FILENAME,
            self.codex_home / INSTRUCTIONS_FILENAME,
        ]
        return [path for path in candidates if path.is_file()]

    def locate_project_config(self, project_root: Path) -> list[Path]:
        candidates = [
            path
            for directory in _project_directories(project_root)
            for path in (
                self.project_config_path(directory),
                directory / INSTRUCTIONS_OVERRIDE_FILENAME,
                directory / INSTRUCTIONS_FILENAME,
            )
        ]
        return [path for path in candidates if path.is_file()]

    def parse(self, path: Path) -> list[Extension]:
        if not path.is_file():
            return []
        if path.name in {INSTRUCTIONS_FILENAME, INSTRUCTIONS_OVERRIDE_FILENAME}:
            # AGENTS.md is authored, not accumulated by the agent: Codex has no
            # auto-memory file of its own (SPECS.md §15).
            return parse_memory_file(
                path, source=self.source, is_persistent_memory=False
            )
        if path.suffix == ".toml":
            return parse_mcp_servers_toml(path, source=self.source)
        logger.warning(f"Codex CLI adapter has no parser for {path}")
        return []

    def serialize(self, extension: Extension) -> str:  # pylint: disable=no-self-use
        return dispatch_serializer(SERIALIZERS, extension)

    @staticmethod
    def walk_up_behavior(extension_type: ExtensionType) -> WalkUpBehavior:
        """Codex consults every directory between the project root and the
        working directory, for both `.codex/config.toml` and `AGENTS.md`
        (learn.chatgpt.com/docs/config-file/config-basic and
        .../agent-configuration/agents-md, fetched 2026-08-14). Config keys are
        overridden by the closest directory; instructions are concatenated.
        """
        return WalkUpBehavior(
            ascends=True,
            stops_at=WalkUpStop.GIT_ROOT,
            merge_semantics=(
                MergeSemantics.CONCATENATE
                if extension_type == ExtensionType.MEMORY_FILE
                else MergeSemantics.OVERRIDE
            ),
        )

    @staticmethod
    def _build_directory_instructions_layers(
        directory: Path, *, scope: Scope, origin: LayerOrigin, ranks: Iterator[int]
    ) -> list[PrecedenceLayer]:
        """The `AGENTS.override.md` / `AGENTS.md` pair one directory contributes.

        Codex reads at most one instructions file per directory — the override
        when it is there, the base file otherwise — so a base file shadowed by
        an override exists on disk without ever resolving.
        """
        override_path = directory / INSTRUCTIONS_OVERRIDE_FILENAME
        base_path = directory / INSTRUCTIONS_FILENAME
        override_exists = override_path.is_file()
        layers: list[PrecedenceLayer] = []
        for path, is_shadowed in ((override_path, False), (base_path, override_exists)):
            exists = path.is_file()
            layers.append(
                ConsultedLayer(
                    scope=scope,
                    file_path=str(path),
                    exists=exists,
                    origin=origin,
                    order_rank=next(ranks),
                    resolves=exists and not is_shadowed,
                )
            )
        return layers

    def precedence_chain(self, project_root: Path | None) -> PrecedenceChain:
        """Codex's stack, highest precedence first: managed config, then CLI
        overrides, then `.codex/config.toml`, the user's `config.toml` and the
        system-wide one, then the instructions files each of those scopes owns.

        Config precedence is quoted from
        learn.chatgpt.com/docs/config-file/config-basic (fetched 2026-08-14);
        managed config outranking CLI overrides is from
        learn.chatgpt.com/docs/enterprise/managed-configuration. The profile
        layer (`~/.codex/<name>.config.toml`, selected at runtime with
        `--profile`) sits between the project and user layers and is not
        reported yet — no static scan can tell which profile is in play.
        """
        ranks = count(1)
        layers: list[PrecedenceLayer] = [
            consulted_file_layer(
                scope=Scope.MANAGED,
                path=self.managed_config_path,
                origin=LayerOrigin.GLOBAL,
                order_rank=next(ranks),
            ),
            # `-c`/`--config` overrides outrank every file except the managed
            # one, but never touch disk, so they can never resolve from a
            # static scan. Scope.GLOBAL stands in for "not a file scope", as it
            # does in the Claude Code adapter.
            ConsultedLayer(
                scope=Scope.GLOBAL,
                file_path=COMMAND_LINE_ARGUMENTS,
                exists=False,
                origin=LayerOrigin.GLOBAL,
                order_rank=next(ranks),
                resolves=False,
            ),
        ]
        directories = _project_directories(project_root) if project_root is not None else ()
        directory_origins = [
            (directory, LayerOrigin.ANCESTOR_DIR if index else LayerOrigin.REGISTERED_PROJECT)
            for index, directory in enumerate(directories)
        ]
        for directory, origin in directory_origins:
            layers.append(
                consulted_file_layer(
                    scope=Scope.PROJECT,
                    path=self.project_config_path(directory),
                    origin=origin,
                    order_rank=next(ranks),
                )
            )
        layers.extend(
            [
                consulted_file_layer(
                    scope=Scope.USER,
                    path=self.user_config_path,
                    origin=LayerOrigin.GLOBAL,
                    order_rank=next(ranks),
                ),
                consulted_file_layer(
                    scope=Scope.MANAGED,
                    path=self.system_config_path,
                    origin=LayerOrigin.GLOBAL,
                    order_rank=next(ranks),
                ),
            ]
        )
        for directory, origin in directory_origins:
            layers.extend(
                self._build_directory_instructions_layers(
                    directory,
                    scope=Scope.PROJECT,
                    origin=origin,
                    ranks=ranks,
                )
            )
        layers.extend(
            self._build_directory_instructions_layers(
                self.codex_home,
                scope=Scope.USER,
                origin=LayerOrigin.GLOBAL,
                ranks=ranks,
            )
        )
        return PrecedenceChain(source=self.source, project_id=None, layers=layers)
