"""Parser for Claude Code memory files."""

from __future__ import annotations

import re

from ..models import Instruction


def parse_memory_file(content: str, filename: str = "") -> list[Instruction]:
    """Parse a memory .md file into an instruction.

    Memory files have YAML frontmatter (name, description, type) and body content.
    """
    frontmatter, body = _split_frontmatter(content)
    if not body.strip():
        return []

    name = frontmatter.get("name", filename)
    mem_type = frontmatter.get("type", "unknown")
    description = frontmatter.get("description", "")

    header = f"Memory: {name} ({mem_type})"
    topic_keywords = _detect_memory_topics(body, mem_type)

    return [Instruction(
        section_header=header,
        section_content=body.strip(),
        topic_keywords=topic_keywords,
        line_start=1,
        line_end=len(content.split("\n")),
    )]


def _split_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Split YAML frontmatter from body content."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        return {}, content

    fm_text = match.group(1)
    body = match.group(2)
    fm: dict[str, str] = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm, body


def _detect_memory_topics(text: str, mem_type: str) -> str:
    """Detect topics from memory content."""
    topics = [mem_type] if mem_type != "unknown" else []
    text_lower = text.lower()
    keyword_map = {
        "testing": ["test", "pytest"],
        "database": ["databricks", "sql", "table"],
        "cli": ["cli", "typer", "--json"],
        "git": ["git", "commit", "branch"],
    }
    for topic, keywords in keyword_map.items():
        for kw in keywords:
            if kw in text_lower:
                topics.append(topic)
                break
    return ",".join(sorted(set(topics)))
