"""Diff detection for skillvault — shows what changed since last scan."""

from __future__ import annotations

import difflib
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from .models import DiffChange, DiffResult
from .storage import Storage


def diff(storage: Storage, since_days: int | None = None) -> DiffResult:
    """Show what changed since the last scan or within a timeframe.

    Compares current filesystem state against what's indexed in the DB.
    """
    if since_days is not None:
        since_dt = datetime.now() - timedelta(days=since_days)
        since_str = since_dt.isoformat()
    else:
        last_scan = storage.get_last_scan()
        if last_scan:
            since_str = last_scan["scanned_at"]
        else:
            since_str = "1970-01-01T00:00:00"

    result = DiffResult(since=since_str)

    active_files = storage.get_all_active_files()

    for frec in active_files:
        fpath = Path(frec.file_path)

        if not fpath.exists():
            # File was deleted from disk
            project = _get_project_name(storage, frec.project_id)
            result.changes["deleted"].append(DiffChange(
                path=frec.file_path,
                project=project,
                type=frec.file_type,
            ))
            continue

        current_content = fpath.read_text(errors="replace")
        current_hash = hashlib.sha256(current_content.encode()).hexdigest()

        if current_hash != frec.content_hash:
            project = _get_project_name(storage, frec.project_id)
            diff_text = _generate_diff(frec.content, current_content, frec.file_path)
            result.changes["modified"].append(DiffChange(
                path=frec.file_path,
                project=project,
                type=frec.file_type,
                diff=diff_text,
                old_hash=frec.content_hash,
                new_hash=current_hash,
            ))

    # Check for new files not yet in DB would require re-scanning roots,
    # which is what `scan` does. Diff only compares indexed vs current.

    result.summary = {
        "new": len(result.changes["new"]),
        "modified": len(result.changes["modified"]),
        "deleted": len(result.changes["deleted"]),
    }

    return result


def _get_project_name(storage: Storage, project_id: int) -> str:
    """Look up project name by ID."""
    row = storage.conn.execute(
        "SELECT name FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return row["name"] if row else "unknown"


def _generate_diff(old_content: str, new_content: str, file_path: str) -> str:
    """Generate a unified diff between old and new content."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff_lines = difflib.unified_diff(
        old_lines, new_lines,
        fromfile="indexed", tofile="current",
        lineterm="",
    )
    return "".join(diff_lines)
