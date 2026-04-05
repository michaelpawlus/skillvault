"""File scanner for discovering and indexing Claude Code configuration files."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .config import (
    get_claude_home,
    get_exclude_patterns,
    get_extra_paths,
    get_file_patterns,
    get_memory_pattern,
    get_scan_roots,
    get_skill_pattern,
)
from .models import ScanResult
from .parsers.claude_md import parse_claude_md
from .parsers.memory import parse_memory_file
from .parsers.settings import parse_settings_file
from .parsers.skill import parse_skill_file
from .storage import Storage


def scan(storage: Storage, config: dict, root_override: str | None = None,
         full: bool = False) -> ScanResult:
    """Discover and index all relevant files.

    Args:
        storage: Database storage instance.
        config: Loaded configuration dict.
        root_override: If set, scan only this root instead of configured roots.
        full: If True, force re-read of all files regardless of hash.
    """
    start = time.monotonic()

    roots = [Path(root_override).expanduser()] if root_override else get_scan_roots(config)
    claude_home = get_claude_home(config)
    exclude_patterns = get_exclude_patterns(config)
    file_patterns = get_file_patterns(config)
    extra_paths = get_extra_paths(config)
    memory_pattern = get_memory_pattern(config)
    skill_pattern = get_skill_pattern(config)

    discovered_files: list[tuple[Path, str, str]] = []  # (path, file_type, project_name)
    discovered_projects: set[str] = set()

    # Scan root directories for CLAUDE.md and settings files
    for root in roots:
        if not root.exists():
            continue
        for pattern in file_patterns:
            for fpath in root.rglob(pattern):
                if _is_excluded(fpath, exclude_patterns):
                    continue
                project_name = _derive_project_name(fpath, root)
                file_type = _classify_file(fpath)
                discovered_files.append((fpath, file_type, project_name))
                discovered_projects.add(project_name)

    # Scan extra paths (global CLAUDE.md, global settings.json)
    for extra in extra_paths:
        if extra.exists():
            file_type = _classify_file(extra)
            discovered_files.append((extra, file_type, "global"))
            discovered_projects.add("global")

    # Scan memory files under claude_home
    if claude_home.exists():
        for fpath in claude_home.glob(memory_pattern):
            project_name = _derive_memory_project(fpath, claude_home)
            discovered_files.append((fpath, "memory", project_name))
            discovered_projects.add(project_name)

        # Scan skill files
        for fpath in claude_home.glob(skill_pattern):
            skill_name = fpath.parent.name
            discovered_files.append((fpath, "skill", f"skill:{skill_name}"))

    # Track which paths we've seen this scan
    seen_paths: set[str] = set()
    counts = {"new": 0, "changed": 0, "unchanged": 0}

    for fpath, file_type, project_name in discovered_files:
        path_str = str(fpath)
        seen_paths.add(path_str)

        content = fpath.read_text(errors="replace")
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        if not full:
            existing = storage.get_file_by_path(path_str)
            if existing and existing.content_hash == content_hash and not existing.is_deleted:
                counts["unchanged"] += 1
                # Still touch last_indexed_at
                storage.upsert_file(
                    project_id=existing.project_id,
                    file_type=file_type,
                    file_path=path_str,
                    content=content,
                    content_hash=content_hash,
                    size_bytes=len(content.encode()),
                )
                continue

        project_id = storage.upsert_project(project_name, str(fpath.parent))
        file_id, status = storage.upsert_file(
            project_id=project_id,
            file_type=file_type,
            file_path=path_str,
            content=content,
            content_hash=content_hash,
            size_bytes=len(content.encode()),
        )

        if full:
            status = "changed"  # treat all as changed in full mode

        counts[status] = counts.get(status, 0) + 1

        # Parse and store instructions
        instructions = _parse_file(content, file_type, fpath)
        if instructions:
            for inst in instructions:
                inst.file_id = file_id
            storage.upsert_instructions(file_id, instructions)

    # Mark deleted files
    deleted_count = 0
    for existing_path in storage.get_active_file_paths():
        if existing_path not in seen_paths:
            if storage.mark_deleted(existing_path):
                deleted_count += 1

    duration_ms = int((time.monotonic() - start) * 1000)
    roots_str = ",".join(str(r) for r in roots)

    scan_id = storage.record_scan(
        roots_scanned=roots_str,
        files_found=len(discovered_files),
        files_new=counts["new"],
        files_changed=counts["changed"],
        files_unchanged=counts["unchanged"],
        files_deleted=deleted_count,
        projects_discovered=len(discovered_projects),
        duration_ms=duration_ms,
    )

    return ScanResult(
        scan_id=scan_id,
        scanned_at="",  # filled by DB
        roots_scanned=[str(r) for r in roots],
        files_found=len(discovered_files),
        new=counts["new"],
        changed=counts["changed"],
        unchanged=counts["unchanged"],
        deleted=deleted_count,
        projects_discovered=len(discovered_projects),
        duration_ms=duration_ms,
    )


def _is_excluded(path: Path, exclude_patterns: list[str]) -> bool:
    """Check if a path contains any excluded directory names."""
    parts = path.parts
    return any(pattern in parts for pattern in exclude_patterns)


def _derive_project_name(fpath: Path, root: Path) -> str:
    """Derive project name from file path relative to scan root."""
    try:
        rel = fpath.relative_to(root)
        # First directory component is the project name
        return rel.parts[0] if len(rel.parts) > 1 else root.name
    except ValueError:
        return fpath.parent.name


def _derive_memory_project(fpath: Path, claude_home: Path) -> str:
    """Derive project name from a memory file path.

    Memory paths look like: ~/.claude/projects/<project-slug>/memory/file.md
    """
    try:
        rel = fpath.relative_to(claude_home / "projects")
        return rel.parts[0] if rel.parts else "unknown"
    except ValueError:
        return "unknown"


def _classify_file(fpath: Path) -> str:
    """Classify a file by its name/path."""
    name = fpath.name
    if name == "CLAUDE.md":
        return "claude-md"
    if name == "settings.json":
        return "settings"
    if name == "SKILL.md":
        return "skill"
    return "memory"


def _parse_file(content: str, file_type: str, fpath: Path):
    """Parse file content into instructions based on type."""
    if file_type == "claude-md":
        return parse_claude_md(content)
    if file_type == "memory":
        return parse_memory_file(content, fpath.stem)
    if file_type == "skill":
        return parse_skill_file(content, fpath.parent.name)
    if file_type == "settings":
        return parse_settings_file(content, str(fpath))
    return []
