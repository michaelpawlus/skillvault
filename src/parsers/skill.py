"""Parser for SKILL.md files."""

from __future__ import annotations

from ..models import Instruction


def parse_skill_file(content: str, skill_name: str = "") -> list[Instruction]:
    """Parse a SKILL.md file into instructions.

    Skills are treated as a single instruction block with the skill name as header.
    """
    if not content.strip():
        return []

    return [Instruction(
        section_header=f"Skill: {skill_name}" if skill_name else "Skill",
        section_content=content.strip(),
        topic_keywords="skill",
        line_start=1,
        line_end=len(content.split("\n")),
    )]
