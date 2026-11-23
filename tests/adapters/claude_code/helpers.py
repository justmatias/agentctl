import json


def agents_md_plugin_settings(plugin_id: str = "cc-plugin-agents-md@builtin") -> str:
    """Settings JSON that tells Claude to load AGENTS.md alongside CLAUDE.md."""
    return json.dumps({
        "pluginConfigs": {
            plugin_id: {"options": {"instructionFiles": "claude-md-and-agents-md"}}
        }
    })
