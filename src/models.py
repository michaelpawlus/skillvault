"""Data models for skillvault."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Project:
    id: int | None = None
    name: str = ""
    path: str = ""
    discovered_at: str = ""
    last_scanned_at: str | None = None
    is_active: bool = True


@dataclass
class FileRecord:
    id: int | None = None
    project_id: int = 0
    file_type: str = ""
    file_path: str = ""
    content: str = ""
    content_hash: str = ""
    size_bytes: int = 0
    first_indexed_at: str = ""
    last_indexed_at: str = ""
    is_deleted: bool = False


@dataclass
class ScanResult:
    scan_id: int = 0
    scanned_at: str = ""
    roots_scanned: list[str] = field(default_factory=list)
    files_found: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    deleted: int = 0
    projects_discovered: int = 0
    duration_ms: int = 0


@dataclass
class SearchResult:
    file_id: int = 0
    project: str = ""
    file_type: str = ""
    file_path: str = ""
    snippet: str = ""
    rank: float = 0.0
    last_scanned: str = ""


@dataclass
class DiffChange:
    path: str = ""
    project: str = ""
    type: str = ""
    diff: str | None = None
    old_hash: str | None = None
    new_hash: str | None = None


@dataclass
class DiffResult:
    since: str = ""
    changes: dict[str, list[DiffChange]] = field(default_factory=lambda: {
        "new": [], "modified": [], "deleted": []
    })
    summary: dict[str, int] = field(default_factory=lambda: {
        "new": 0, "modified": 0, "deleted": 0
    })


@dataclass
class Instruction:
    id: int | None = None
    file_id: int = 0
    section_header: str = ""
    section_content: str = ""
    topic_keywords: str = ""
    line_start: int = 0
    line_end: int = 0


@dataclass
class Overlap:
    topic: str = ""
    keyword_matches: list[str] = field(default_factory=list)
    instructions: list[dict] = field(default_factory=list)


@dataclass
class ConflictResult:
    topics_analyzed: int = 0
    overlaps_found: int = 0
    overlaps: list[Overlap] = field(default_factory=list)


@dataclass
class Profile:
    id: int | None = None
    name: str = ""
    include_patterns: str = ""
    project_names: str = ""
    created_at: str = ""
    updated_at: str = ""
