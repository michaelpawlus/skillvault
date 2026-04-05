"""Export curated instruction sets from indexed content."""

from __future__ import annotations

import fnmatch
import io
import json
import zipfile

from .config import get_profiles
from .storage import Storage


def export_profile(storage: Storage, config: dict, profile_name: str,
                   fmt: str = "claude-md") -> str | bytes:
    """Export a profile as a merged CLAUDE.md or a zip archive.

    Args:
        storage: Database storage instance.
        config: Loaded configuration dict.
        profile_name: Name of the profile to export.
        fmt: Output format — 'claude-md' or 'archive'.

    Returns:
        String content for claude-md format, bytes for archive format.

    Raises:
        ValueError: If profile not found or format invalid.
    """
    profiles = get_profiles(config)
    if profile_name not in profiles:
        raise ValueError(f"Profile '{profile_name}' not found in config")

    profile = profiles[profile_name]
    include_patterns = profile.get("include_patterns", [])
    project_names = profile.get("project_names", [])

    # Gather matching files
    all_files = storage.get_all_active_files()
    matched_files = []

    for f in all_files:
        # Check project name match
        project = _get_project_name(storage, f.project_id)
        project_match = not project_names or project in project_names

        # Check content pattern match
        pattern_match = not include_patterns or any(
            fnmatch.fnmatch(f.content, pat) for pat in include_patterns
        )

        if project_match and pattern_match:
            matched_files.append((f, project))

    if fmt == "claude-md":
        return _export_as_claude_md(matched_files, profile_name)
    elif fmt == "archive":
        return _export_as_archive(matched_files, profile_name)
    else:
        raise ValueError(f"Unknown format: {fmt}")


def _export_as_claude_md(matched_files: list, profile_name: str) -> str:
    """Merge matched files into a single CLAUDE.md document."""
    sections: list[str] = []
    sections.append(f"# Exported Profile: {profile_name}\n")
    sections.append(f"_Contains {len(matched_files)} source file(s)._\n")

    for f, project in matched_files:
        sections.append(f"---\n\n## Source: {project} ({f.file_type})\n")
        sections.append(f"_From: {f.file_path}_\n")
        sections.append(f.content)
        sections.append("")

    return "\n".join(sections)


def _export_as_archive(matched_files: list, profile_name: str) -> bytes:
    """Pack matched files into a zip archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {"profile": profile_name, "files": []}
        for f, project in matched_files:
            archive_path = f"{project}/{f.file_type}/{f.file_path.split('/')[-1]}"
            zf.writestr(archive_path, f.content)
            manifest["files"].append({
                "project": project,
                "file_type": f.file_type,
                "archive_path": archive_path,
                "original_path": f.file_path,
            })
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return buf.getvalue()


def _get_project_name(storage: Storage, project_id: int) -> str:
    row = storage.conn.execute(
        "SELECT name FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return row["name"] if row else "unknown"
