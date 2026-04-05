"""Conflict detection — surfaces overlapping instructions across projects."""

from __future__ import annotations

from collections import defaultdict

from .models import ConflictResult, Overlap
from .storage import Storage


def detect_conflicts(storage: Storage, topic_filter: str | None = None) -> ConflictResult:
    """Detect overlapping instructions across different projects.

    Groups instructions by topic keywords, then within each topic finds
    instructions from different projects that address the same topic.
    """
    all_instructions = storage.get_all_instructions()

    # Group by topic
    topic_groups: dict[str, list[dict]] = defaultdict(list)
    for inst in all_instructions:
        keywords = inst.get("topic_keywords", "") or ""
        for topic in keywords.split(","):
            topic = topic.strip()
            if topic:
                if topic_filter and topic_filter.lower() != topic.lower():
                    continue
                topic_groups[topic].append(inst)

    overlaps: list[Overlap] = []
    topics_analyzed = len(topic_groups)

    for topic, instructions in sorted(topic_groups.items()):
        # Group by project within this topic
        by_project: dict[str, list[dict]] = defaultdict(list)
        for inst in instructions:
            by_project[inst["project_name"]].append(inst)

        # Only flag as overlap if multiple projects cover this topic
        if len(by_project) < 2:
            continue

        # Extract keyword matches from the topic
        keyword_matches = [topic]
        for inst in instructions:
            kw = (inst.get("topic_keywords") or "").split(",")
            keyword_matches.extend(k.strip() for k in kw if k.strip())
        keyword_matches = sorted(set(keyword_matches))

        overlap_instructions = []
        for project_name, project_insts in sorted(by_project.items()):
            for inst in project_insts:
                overlap_instructions.append({
                    "project": project_name,
                    "file": inst["file_path"],
                    "section": inst["section_header"],
                    "text": inst["section_content"],
                })

        overlaps.append(Overlap(
            topic=topic,
            keyword_matches=keyword_matches,
            instructions=overlap_instructions,
        ))

    return ConflictResult(
        topics_analyzed=topics_analyzed,
        overlaps_found=len(overlaps),
        overlaps=overlaps,
    )
