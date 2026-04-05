"""Parser for CLAUDE.md files — extracts sections as instructions."""

from __future__ import annotations

import re

from ..models import Instruction

# Topic keywords mapped to regex patterns
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "testing": ["pytest", "test", "coverage", "assert", "mock", "fixture"],
    "git": ["git", "commit", "branch", "push", "merge", "rebase", "pr", "pull request"],
    "database": ["sql", "database", "table", "query", "databricks", "postgres", "sqlite", "migration"],
    "cli": ["cli", "typer", "argparse", "command", "--json", "flag", "argument"],
    "style": ["format", "lint", "ruff", "black", "style", "convention", "naming"],
    "deployment": ["deploy", "ci", "cd", "github actions", "pipeline", "release"],
    "dependencies": ["pip", "install", "dependency", "requirements", "package", "venv"],
    "agent": ["agent", "claude", "obsidian", "memory", "skill", "hook"],
}


def parse_claude_md(content: str) -> list[Instruction]:
    """Parse a CLAUDE.md file into section-based instructions."""
    lines = content.split("\n")
    instructions: list[Instruction] = []
    current_header = ""
    current_lines: list[str] = []
    header_start = 0

    for i, line in enumerate(lines):
        header_match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if header_match:
            if current_header and current_lines:
                section_content = "\n".join(current_lines).strip()
                if section_content:
                    instructions.append(Instruction(
                        section_header=current_header,
                        section_content=section_content,
                        topic_keywords=_detect_topics(current_header + " " + section_content),
                        line_start=header_start + 1,
                        line_end=i,
                    ))
            current_header = header_match.group(2).strip()
            current_lines = []
            header_start = i
        else:
            current_lines.append(line)

    # Last section
    if current_header and current_lines:
        section_content = "\n".join(current_lines).strip()
        if section_content:
            instructions.append(Instruction(
                section_header=current_header,
                section_content=section_content,
                topic_keywords=_detect_topics(current_header + " " + section_content),
                line_start=header_start + 1,
                line_end=len(lines),
            ))

    return instructions


def _detect_topics(text: str) -> str:
    """Detect topic keywords from text content."""
    text_lower = text.lower()
    matched: list[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                matched.append(topic)
                break
    return ",".join(sorted(set(matched)))
