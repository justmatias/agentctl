from pathlib import Path

from agentctl.adapters import CodexCliAdapter


def codex_adapter_at(home: Path) -> CodexCliAdapter:
    """An adapter whose every machine-wide path stays inside `home`.

    Nothing a test runs may stat the developer's real `~/.codex` or `/etc/codex`,
    so both directories are always redirected into the scenario's home.
    """
    return CodexCliAdapter(
        codex_home=home / ".codex",
        system_config_directory=home / "system-config",
    )
