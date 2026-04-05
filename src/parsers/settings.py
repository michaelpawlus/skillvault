"""Parser for .claude/settings.json — extracts hook configurations."""

from __future__ import annotations

import json

from ..models import Instruction


def parse_settings_file(content: str, file_path: str = "") -> list[Instruction]:
    """Parse a settings.json file and extract hook definitions.

    Hooks in settings.json look like:
    {
      "hooks": {
        "PreToolUse": [...],
        "PostToolUse": [...],
        ...
      }
    }
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    instructions: list[Instruction] = []

    hooks = data.get("hooks", {})
    if hooks:
        for event_name, hook_list in hooks.items():
            if not isinstance(hook_list, list):
                continue
            hook_text = json.dumps(hook_list, indent=2)
            instructions.append(Instruction(
                section_header=f"Hook: {event_name}",
                section_content=hook_text,
                topic_keywords="hook,agent",
                line_start=1,
                line_end=len(content.split("\n")),
            ))

    # Also capture any other top-level settings of interest
    for key in ("permissions", "env", "model"):
        if key in data:
            instructions.append(Instruction(
                section_header=f"Setting: {key}",
                section_content=json.dumps(data[key], indent=2),
                topic_keywords="settings",
                line_start=1,
                line_end=len(content.split("\n")),
            ))

    return instructions
