"""Tests for scanner module."""

from pathlib import Path

from src.scanner import scan
from src.storage import Storage


def test_scan_discovers_files(tmp_path, fixtures_dir):
    db_path = tmp_path / "test.db"
    storage = Storage(db_path)
    config = {
        "scan": {
            "roots": [str(fixtures_dir)],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": [],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
    }
    result = scan(storage, config)
    assert result.files_found >= 2  # project_a and project_b
    assert result.new >= 2
    storage.close()


def test_scan_idempotent(tmp_path, fixtures_dir):
    db_path = tmp_path / "test.db"
    storage = Storage(db_path)
    config = {
        "scan": {
            "roots": [str(fixtures_dir)],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": [],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
    }
    result1 = scan(storage, config)
    result2 = scan(storage, config)
    assert result2.new == 0
    assert result2.unchanged == result1.files_found
    storage.close()


def test_scan_detects_changes(tmp_path):
    # Create a project dir with a CLAUDE.md
    proj_dir = tmp_path / "projects" / "myproj"
    proj_dir.mkdir(parents=True)
    claude_md = proj_dir / "CLAUDE.md"
    claude_md.write_text("# Original")

    db_path = tmp_path / "test.db"
    storage = Storage(db_path)
    config = {
        "scan": {
            "roots": [str(tmp_path / "projects")],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": [],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
    }
    scan(storage, config)
    claude_md.write_text("# Modified content")
    result = scan(storage, config)
    assert result.changed == 1
    storage.close()


def test_scan_root_override(tmp_path, fixtures_dir):
    db_path = tmp_path / "test.db"
    storage = Storage(db_path)
    config = {
        "scan": {
            "roots": ["/nonexistent"],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": [],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
    }
    result = scan(storage, config, root_override=str(fixtures_dir))
    assert result.files_found >= 2
    storage.close()


def test_scan_marks_deleted(tmp_path):
    proj_dir = tmp_path / "projects" / "myproj"
    proj_dir.mkdir(parents=True)
    claude_md = proj_dir / "CLAUDE.md"
    claude_md.write_text("# Test")

    db_path = tmp_path / "test.db"
    storage = Storage(db_path)
    config = {
        "scan": {
            "roots": [str(tmp_path / "projects")],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": [],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
    }
    scan(storage, config)
    claude_md.unlink()
    result = scan(storage, config)
    assert result.deleted == 1
    storage.close()


def test_scan_excludes_patterns(tmp_path):
    proj_dir = tmp_path / "projects" / "myproj" / "node_modules" / "dep"
    proj_dir.mkdir(parents=True)
    (proj_dir / "CLAUDE.md").write_text("# Should be excluded")

    real_dir = tmp_path / "projects" / "myproj"
    (real_dir / "CLAUDE.md").write_text("# Should be included")

    db_path = tmp_path / "test.db"
    storage = Storage(db_path)
    config = {
        "scan": {
            "roots": [str(tmp_path / "projects")],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": ["node_modules"],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
    }
    result = scan(storage, config)
    assert result.files_found == 1
    storage.close()
