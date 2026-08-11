from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    """Canonical shape for a memory/instruction file"""

    model_config = ConfigDict(extra="forbid")

    content: str
    is_persistent_memory: bool = Field(
        description="True for agent-accumulated memory eg. MEMORY.MD"
    )


class SkillConfig(BaseModel):
    """Canonical shape for a SKILL.md-style skill"""

    model_config = ConfigDict(extra="forbid")

    description: str
    body: str
    bundled_files: list[str] = []


CanonicalConfig = McpServerConfig | MemoryFileConfig | SkillConfig
