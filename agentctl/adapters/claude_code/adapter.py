import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

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
)
from agentctl.utils import logger

from .serializers import SERIALIZERS


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

    @staticmethod
    def _slugify_project_path(project_root: Path) -> str:
        """Best-effort match of the directory naming Claude Code uses under
        `~/.claude/projects/<slug>/` for a project's auto-memory.

        Real Claude Code derives `<slug>` from the project's git repository root
        so worktrees of the same repo share one memory directory; this adapter
        has no git awareness and slugifies `project_root` itself instead, which
        only matches for a plain (non-worktree) checkout.
        """
        return re.sub(r"[^A-Za-z0-9]", "-", str(project_root))

    def auto_memory_path(self, project_root: Path) -> Path:
        """Where Claude Code stores a project's user-scoped auto-memory (SPECS.md §15)."""
        return (
            self.home
            / ".claude"
            / "projects"
            / self._slugify_project_path(project_root)
            / "memory"
            / "MEMORY.md"
        )

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
            layers.append(
                consulted_file_layer(
                    scope=Scope.LOCAL,
                    path=self.local_settings_path(project_root),
                    origin=LayerOrigin.REGISTERED_PROJECT,
                    order_rank=3,
                )
            )
            layers.append(
                consulted_file_layer(
                    scope=Scope.PROJECT,
                    path=self.project_settings_path(project_root),
                    origin=LayerOrigin.REGISTERED_PROJECT,
                    order_rank=4,
                )
            )

        layers.append(
            consulted_file_layer(
                scope=Scope.USER,
                path=self.user_settings_path,
                origin=LayerOrigin.GLOBAL,
                order_rank=5,
            )
        )

        # Verified against current Claude Code docs (code.claude.com/docs/en/memory,
        # "AGENTS.md" section, fetched 2026-08-13): "Claude Code reads CLAUDE.md,
        # not AGENTS.md." Confirmed not_consulted, not unconfirmed (SPECS.md §5.1).
        agents_md_path = (
            (project_root / "AGENTS.md")
            if project_root is not None
            else (self.home / "AGENTS.md")
        )
        layers.append(
            NotConsultedLayer(
                scope=Scope.GLOBAL,
                file_path=str(agents_md_path),
                exists=agents_md_path.is_file(),
                origin=(
                    LayerOrigin.REGISTERED_PROJECT
                    if project_root is not None
                    else LayerOrigin.GLOBAL
                ),
            )
        )
        return PrecedenceChain(source=self.source, project_id=None, layers=layers)
