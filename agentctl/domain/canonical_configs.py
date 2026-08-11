"""Normalized, harness-independent config shapes per extension type (SPECS.md §8, §13.2)."""

from pydantic import BaseModel, ConfigDict, model_validator


class McpServerConfig(BaseModel):
    """Canonical shape for an MCP server, covering stdio and remote transports."""

    model_config = ConfigDict(extra="forbid")

    command: str | None = None
    args: list[str] = []
    env: dict[str, str] = {}
    url: str | None = None
    headers: dict[str, str] = {}

    @model_validator(mode="after")
    def _require_command_or_url(self) -> "McpServerConfig":
        if not self.command and not self.url:
            raise ValueError("McpServerConfig requires either 'command' or 'url'")
        return self


class MemoryFileConfig(BaseModel):
    """Canonical shape for a memory/instruction file (SPECS §7.5)."""

    model_config = ConfigDict(extra="forbid")

    content: str
    is_persistent_memory: bool
    """True for agent-accumulated memory (e.g. MEMORY.md); False for
    developer-authored instruction/rule files (e.g. CLAUDE.md, AGENTS.md)."""


class SkillConfig(BaseModel):
    """Canonical shape for a `SKILL.md`-style skill (SPECS §7.12.1)."""

    model_config = ConfigDict(extra="forbid")

    description: str
    body: str
    bundled_files: list[str] = []


CanonicalConfig = McpServerConfig | MemoryFileConfig | SkillConfig
