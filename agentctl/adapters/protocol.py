from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

from agentctl.domain import Extension, ExtensionType, PrecedenceChain, Scope, Source


class MergeSemantics(str, Enum):
    """How a source combines multiple layers that define the same key."""

    OVERRIDE = "override"
    CONCATENATE = "concatenate"


class WalkUpStop(str, Enum):
    """Where a source's directory ascent for a given extension type stops."""

    GIT_ROOT = "git_root"
    HOME_DIRECTORY = "home_directory"
    FILESYSTEM_ROOT = "filesystem_root"
    NONE = "none"
    """Does not ascend at all — only the given directory is consulted."""


class WorkflowTargetForm(str, Enum):
    """Compilation targets a workflow can compile down to (SPECS §7.12.2)."""

    SKILL = "skill"
    SLASH_COMMAND = "slash_command"
    PROMPT_FILE = "prompt_file"
    SUB_AGENT = "sub_agent"


@dataclass(frozen=True)
class WalkUpBehavior:
    """A source's directory walk-up contract for one extension type (SPECS §7.9).

    Never inferred from the directory tree — always adapter-reported.
    """

    ascends: bool
    stops_at: WalkUpStop
    merge_semantics: MergeSemantics


@dataclass(frozen=True)
class AdapterCapabilities:
    """What an adapter supports, so the UI derives capability from adapters
    rather than hardcoding it (SPECS §9)."""

    source: Source
    extension_types: frozenset[ExtensionType]
    scopes: frozenset[Scope]
    workflow_target_forms: frozenset[WorkflowTargetForm] = field(default_factory=frozenset)


@runtime_checkable
class SourceAdapter(Protocol):
    """One adapter per source — a harness, or the shared `.agents` convention.

    SPECS.md §9 lists six adapter responsibilities: locate global-scope config,
    locate project-scope config, parse to canonical shape, serialize back to
    native format, report an ordered precedence chain — including directory
    walk-up behavior and merge semantics per §7.9 — and declare capabilities
    (extension types, scopes, workflow target forms per §7.12.2), so the rest
    of the tool never hardcodes harness-specific behavior.
    """

    @property
    def source(self) -> Source:
        """The source this adapter speaks for.

        Declared read-only so an adapter can pin it as a `ClassVar` — it is
        fixed per adapter class, never per instance.
        """

    def locate_global_config(self) -> list[Path]:
        """Every global-scope config path this source actually has on disk."""

    def locate_project_config(self, project_root: Path) -> list[Path]:
        """Every project-scope config path this source has under `project_root`."""

    def parse(self, path: Path) -> list[Extension]:
        """Parse a located file into canonical Extension records."""

    def serialize(self, extension: Extension) -> str:
        """Render a canonical Extension into this source's native format."""

    def walk_up_behavior(self, extension_type: ExtensionType) -> WalkUpBehavior:
        """This source's directory walk-up and merge contract for `extension_type`."""

    def precedence_chain(self, project_root: Path | None) -> PrecedenceChain:
        """The ordered layer stack for `project_root` (None = global view).

        `PrecedenceChain.project_id` is left unset: the adapter has no
        knowledge of the Project registry. The core service attaches the
        registered Project's id when it persists this chain.
        """

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Extension types, scopes, and workflow target forms this adapter supports."""
