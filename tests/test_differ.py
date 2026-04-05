"""Tests for differ module."""

import hashlib
from pathlib import Path

from src.differ import diff
from src.storage import Storage


def test_diff_no_changes(tmp_path):
    proj_dir = tmp_path / "projects" / "myproj"
    proj_dir.mkdir(parents=True)
    claude_md = proj_dir / "CLAUDE.md"
    content = "# My Project"
    claude_md.write_text(content)

    db_path = tmp_path / "test.db"
    storage = Storage(db_path)
    pid = storage.upsert_project("myproj", str(proj_dir))
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    storage.upsert_file(pid, "claude-md", str(claude_md), content,
                         content_hash, len(content.encode()))
    storage.record_scan("roots", 1, 1, 0, 0, 0, 1, 10)

    result = diff(storage)
    assert result.summary["modified"] == 0
    assert result.summary["deleted"] == 0
    storage.close()


def test_diff_detects_modification(tmp_path):
    proj_dir = tmp_path / "projects" / "myproj"
    proj_dir.mkdir(parents=True)
    claude_md = proj_dir / "CLAUDE.md"
    old_content = "# Original"
    claude_md.write_text(old_content)

    db_path = tmp_path / "test.db"
    storage = Storage(db_path)
    pid = storage.upsert_project("myproj", str(proj_dir))
    old_hash = hashlib.sha256(old_content.encode()).hexdigest()
    storage.upsert_file(pid, "claude-md", str(claude_md), old_content,
                         old_hash, len(old_content.encode()))

    # Now modify the file on disk
    claude_md.write_text("# Modified")

    result = diff(storage)
    assert result.summary["modified"] == 1
    assert result.changes["modified"][0].project == "myproj"
    assert result.changes["modified"][0].diff is not None
    storage.close()


def test_diff_detects_deletion(tmp_path):
    proj_dir = tmp_path / "projects" / "myproj"
    proj_dir.mkdir(parents=True)
    claude_md = proj_dir / "CLAUDE.md"
    content = "# Will be deleted"
    claude_md.write_text(content)

    db_path = tmp_path / "test.db"
    storage = Storage(db_path)
    pid = storage.upsert_project("myproj", str(proj_dir))
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    storage.upsert_file(pid, "claude-md", str(claude_md), content,
                         content_hash, len(content.encode()))

    claude_md.unlink()

    result = diff(storage)
    assert result.summary["deleted"] == 1
    storage.close()


def test_diff_with_since_days(tmp_path):
    proj_dir = tmp_path / "projects" / "myproj"
    proj_dir.mkdir(parents=True)
    claude_md = proj_dir / "CLAUDE.md"
    content = "# Test"
    claude_md.write_text(content)

    db_path = tmp_path / "test.db"
    storage = Storage(db_path)
    pid = storage.upsert_project("myproj", str(proj_dir))
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    storage.upsert_file(pid, "claude-md", str(claude_md), content,
                         content_hash, len(content.encode()))

    result = diff(storage, since_days=7)
    assert result.since is not None
    storage.close()
