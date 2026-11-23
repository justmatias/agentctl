import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field, ValidationError

from agentctl.adapters.common import (
    consulted_file_layer,
    dispatch_serializer,
    parse_mcp_servers_json,
    parse_memory_file,
    parse_skill,
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
    NotConsultedLayer,
    PrecedenceChain,
    PrecedenceLayer,
    Scope,
    Source,
    UnconfirmedLayer,
)
from agentctl.utils import logger

from .serializers import SERIALIZERS

# Older Claude Code versions use the second ID; newer versions read either.
# https://code.claude.com/docs/en/memory#when-claude-code-reads-agents-md
AGENTS_MD_PLUGIN_IDS = ("cc-plugin-agents-md@builtin", "agents-md@builtin")


class _InstructionFilesOptions(BaseModel):
    instruction_files: str | None = Field(default=None, alias="instructionFiles")


class _PluginConfig(BaseModel):
    options: _InstructionFilesOptions = _InstructionFilesOptions()


class _PluginSettings(BaseModel):
    plugin_configs: dict[str, _PluginConfig] = Field(
        default_factory=dict, alias="pluginConfigs"
    )


def default_managed_settings_path() -> Path:
    return platform_specific_path(
        darwin=Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
        windows=Path(r"C:\Program Files\ClaudeCode\managed-settings.json"),
        default=Path("/etc/claude-code/managed-settings.json"),
    )


@dataclass(kw_only=True)
class ClaudeCodeAdapter:
    """Reads Claude Code's on-disk config into canonical `Extension` records"""

    source: ClassVar[Source] = Source.CLAUDE_CODE
    home: Path = field(default_factory=Path.home)
    managed_settings_path: Path = field(default_factory=default_managed_settings_path)

    @property
    def user_settings_path(self) -> Path:
        return self.home / ".claude" / "settings.json"

    @staticmethod
    def project_settings_path(project_root: Path) -> Path:
        return project_root / ".claude" / "settings.json"

    @staticmethod
    def local_settings_path(project_root: Path) -> Path:
        return project_root / ".claude" / "settings.local.json"

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            source=Source.CLAUDE_CODE,
            extension_types=frozenset({
                ExtensionType.MCP_SERVER,
                ExtensionType.MEMORY_FILE,
                ExtensionType.SKILL,
            }),
            scopes=frozenset({
                Scope.MANAGED,
                Scope.LOCAL,
                Scope.PROJECT,
                Scope.USER,
                Scope.GLOBAL,
            }),
            workflow_target_forms=frozenset({WorkflowTargetForm.SKILL}),
        )

    def auto_memory_path(self, project_root: Path) -> Path:
        """Where Claude Code stores a project's user-scoped auto-memory (SPECS.md §15)."""
        # Real Claude Code derives the `<slug>` directory name from the project's
        # git repository root so worktrees of the same repo share one memory
        # directory; this adapter has no git awareness and slugifies
        # `project_root` itself instead, which only matches for a plain
        # (non-worktree) checkout.
        slug = re.sub(r"[^A-Za-z0-9]", "-", str(project_root))
        return self.home / ".claude" / "projects" / slug / "memory" / "MEMORY.md"

    def instruction_files_setting(self) -> str | None:
        """The `instructionFiles` option, which Claude reads only from managed
        and user settings, managed first."""
        for path in (self.managed_settings_path, self.user_settings_path):
            if not path.is_file():
                continue
            try:
                settings = _PluginSettings.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeDecodeError, ValidationError) as exc:
                logger.warning(f"Skipping unreadable settings in {path}: {exc}")
                continue
            for plugin_id in AGENTS_MD_PLUGIN_IDS:
                plugin = settings.plugin_configs.get(plugin_id)
                if plugin is not None and plugin.options.instruction_files is not None:
                    return plugin.options.instruction_files
        return None

    def locate_global_config(self) -> list[Path]:
        candidates = [
            self.home / ".claude.json",
            self.user_settings_path,
            self.home / ".claude" / "CLAUDE.md",
        ]
        return [path for path in candidates if path.is_file()]

    def locate_project_config(self, project_root: Path) -> list[Path]:
        candidates = [
            self.project_settings_path(project_root),
            self.local_settings_path(project_root),
            project_root / "CLAUDE.md",
            project_root / ".claude" / "memory" / "MEMORY.md",
            self.auto_memory_path(project_root),
        ]
        paths = [path for path in candidates if path.is_file()]
        skills_directory = project_root / ".claude" / "skills"
        if skills_directory.is_dir():
            paths.extend(sorted(skills_directory.glob("*/SKILL.md")))
        return paths

    def parse(self, path: Path) -> list[Extension]:
        if not path.is_file():
            return []
        if path.name == "SKILL.md":
            return parse_skill(path, source=self.source)
        if path.name in {"CLAUDE.md", "MEMORY.md"}:
            return parse_memory_file(
                path,
                source=self.source,
                is_persistent_memory=path.name == "MEMORY.md",
            )
        if path.suffix == ".json":
            return parse_mcp_servers_json(path, source=self.source)
        logger.warning(f"Claude Code adapter has no parser for {path}")
        return []

    def serialize(self, extension: Extension) -> str:  # pylint: disable=no-self-use
        return dispatch_serializer(SERIALIZERS, extension)

    @staticmethod
    def walk_up_behavior(extension_type: ExtensionType) -> WalkUpBehavior:
        if extension_type == ExtensionType.MEMORY_FILE:
            return WalkUpBehavior(
                ascends=True,
                stops_at=WalkUpStop.FILESYSTEM_ROOT,
                merge_semantics=MergeSemantics.CONCATENATE,
            )
        return WalkUpBehavior(
            ascends=False,
            stops_at=WalkUpStop.NONE,
            merge_semantics=MergeSemantics.OVERRIDE,
        )

    def precedence_chain(self, project_root: Path | None) -> PrecedenceChain:
        layers: list[PrecedenceLayer] = [
            consulted_file_layer(
                scope=Scope.MANAGED,
                path=self.managed_settings_path,
                origin=LayerOrigin.GLOBAL,
                order_rank=1,
            ),
            # Command-line arguments rank above every file-backed layer but are
            # never persisted on disk, so they can never resolve from a static
            # scan. Scope.GLOBAL is reused here as the only Scope value not
            # already claimed by one of Claude Code's four file-backed scopes.
            ConsultedLayer(
                scope=Scope.GLOBAL,
                file_path="(command-line arguments)",
                exists=False,
                origin=LayerOrigin.GLOBAL,
                order_rank=2,
                resolves=False,
            ),
        ]

        if project_root:
            layers.extend(
                [
                    consulted_file_layer(
                        scope=Scope.LOCAL,
                        path=self.local_settings_path(project_root),
                        origin=LayerOrigin.REGISTERED_PROJECT,
                        order_rank=3,
                    ),
                    consulted_file_layer(
                        scope=Scope.PROJECT,
                        path=self.project_settings_path(project_root),
                        origin=LayerOrigin.REGISTERED_PROJECT,
                        order_rank=4,
                    ),
                ]
            )

        layers.append(
            consulted_file_layer(
                scope=Scope.USER,
                path=self.user_settings_path,
                origin=LayerOrigin.GLOBAL,
                order_rank=5,
            )
        )

        # https://code.claude.com/docs/en/memory#choose-where-to-put-claude-md-files
        if project_root is not None:
            layers.extend(
                consulted_file_layer(
                    scope=Scope.PROJECT,
                    path=project_root / filename,
                    origin=LayerOrigin.REGISTERED_PROJECT,
                    order_rank=rank,
                )
                for rank, filename in enumerate(
                    ("CLAUDE.local.md", ".claude/CLAUDE.md", "CLAUDE.md"), start=6
                )
            )
        layers.append(
            consulted_file_layer(
                scope=Scope.USER,
                path=self.home / ".claude" / "CLAUDE.md",
                origin=LayerOrigin.GLOBAL,
                order_rank=9,
            )
        )
        if project_root is not None:
            layers.append(
                consulted_file_layer(
                    scope=Scope.USER,
                    path=self.auto_memory_path(project_root),
                    origin=LayerOrigin.REGISTERED_PROJECT,
                    order_rank=10,
                )
            )
            agents_path = project_root / "AGENTS.md"
            if self.instruction_files_setting() == "claude-md-and-agents-md":
                layers.append(
                    consulted_file_layer(
                        scope=Scope.PROJECT,
                        path=agents_path,
                        origin=LayerOrigin.REGISTERED_PROJECT,
                        order_rank=11,
                    )
                )
            else:
                # Without that setting, direct AGENTS.md support depends on the
                # Claude version and on whether a CLAUDE.md exists.
                layers.append(
                    UnconfirmedLayer(
                        scope=Scope.PROJECT,
                        file_path=str(agents_path),
                        exists=agents_path.is_file(),
                        origin=LayerOrigin.REGISTERED_PROJECT,
                    )
                )
        else:
            agents_path = self.home / "AGENTS.md"
            layers.append(
                NotConsultedLayer(
                    scope=Scope.GLOBAL,
                    file_path=str(agents_path),
                    exists=agents_path.is_file(),
                    origin=LayerOrigin.GLOBAL,
                )
            )
        return PrecedenceChain(source=self.source, project_id=None, layers=layers)
