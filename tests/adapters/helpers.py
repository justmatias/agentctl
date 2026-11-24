import json


def render_instruction_files_settings_json(
    value: str = "claude-md-and-agents-md",
    plugin_id: str = "cc-plugin-agents-md@builtin",
) -> str:
    """Settings JSON that sets which instruction files Claude loads."""
    return json.dumps({
        "pluginConfigs": {plugin_id: {"options": {"instructionFiles": value}}}
    })
