"""Shared test fixtures for skillvault."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from src.config import DEFAULT_CONFIG
from src.storage import Storage


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory."""
    return tmp_path


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def storage(db_path):
    """Provide a fresh Storage instance."""
    s = Storage(db_path)
    yield s
    s.close()


@pytest.fixture
def fixtures_dir():
    """Path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_config(tmp_path, fixtures_dir):
    """Provide a config dict pointing to test fixtures."""
    return {
        "general": {
            "db_path": str(tmp_path / "test.db"),
            "log_level": "info",
        },
        "scan": {
            "roots": [str(fixtures_dir)],
            "extra_paths": [],
            "claude_home": str(tmp_path / "claude_home"),
            "exclude_patterns": ["node_modules", ".venv", "__pycache__", ".git"],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
        "profiles": {
            "test-profile": {
                "include_patterns": ["*"],
                "project_names": [],
            },
        },
    }


@pytest.fixture
def populated_storage(storage, fixtures_dir):
    """Storage with some pre-indexed data from fixtures."""
    proj_a_id = storage.upsert_project("project_a", str(fixtures_dir / "project_a"))
    proj_b_id = storage.upsert_project("project_b", str(fixtures_dir / "project_b"))

    content_a = (fixtures_dir / "project_a" / "CLAUDE.md").read_text()
    content_b = (fixtures_dir / "project_b" / "CLAUDE.md").read_text()

    import hashlib
    hash_a = hashlib.sha256(content_a.encode()).hexdigest()
    hash_b = hashlib.sha256(content_b.encode()).hexdigest()

    storage.upsert_file(proj_a_id, "claude-md",
                        str(fixtures_dir / "project_a" / "CLAUDE.md"),
                        content_a, hash_a, len(content_a.encode()))
    storage.upsert_file(proj_b_id, "claude-md",
                        str(fixtures_dir / "project_b" / "CLAUDE.md"),
                        content_b, hash_b, len(content_b.encode()))

    return storage
