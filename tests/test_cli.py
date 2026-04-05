"""Tests for CLI commands."""

import json
from unittest.mock import patch

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def test_scan_command(tmp_path, fixtures_dir):
    config = {
        "general": {"db_path": str(tmp_path / "test.db")},
        "scan": {
            "roots": [str(fixtures_dir)],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": [],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
        "profiles": {},
    }
    with patch("src.cli.load_config", return_value=config):
        result = runner.invoke(app, ["scan", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["files_found"] >= 2


def test_search_command(tmp_path, fixtures_dir):
    config = {
        "general": {"db_path": str(tmp_path / "test.db")},
        "scan": {
            "roots": [str(fixtures_dir)],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": [],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
        "profiles": {},
    }
    with patch("src.cli.load_config", return_value=config):
        # First scan to populate
        runner.invoke(app, ["scan"])
        result = runner.invoke(app, ["search", "pytest", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "results" in data


def test_projects_command(tmp_path, fixtures_dir):
    config = {
        "general": {"db_path": str(tmp_path / "test.db")},
        "scan": {
            "roots": [str(fixtures_dir)],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": [],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
        "profiles": {},
    }
    with patch("src.cli.load_config", return_value=config):
        runner.invoke(app, ["scan"])
        result = runner.invoke(app, ["projects", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total"] >= 2


def test_show_command(tmp_path, fixtures_dir):
    config = {
        "general": {"db_path": str(tmp_path / "test.db")},
        "scan": {
            "roots": [str(fixtures_dir)],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": [],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
        "profiles": {},
    }
    with patch("src.cli.load_config", return_value=config):
        runner.invoke(app, ["scan"])
        result = runner.invoke(app, ["show", "project_a", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["project"]["name"] == "project_a"


def test_show_not_found(tmp_path):
    config = {
        "general": {"db_path": str(tmp_path / "test.db")},
        "scan": {"roots": [], "extra_paths": [], "claude_home": str(tmp_path),
                 "exclude_patterns": [], "file_patterns": ["CLAUDE.md"],
                 "memory_pattern": "p/*/m/*.md", "skill_pattern": "s/*/S.md"},
        "profiles": {},
    }
    with patch("src.cli.load_config", return_value=config):
        result = runner.invoke(app, ["show", "nonexistent", "--json"])
        assert result.exit_code == 2


def test_diff_command(tmp_path, fixtures_dir):
    config = {
        "general": {"db_path": str(tmp_path / "test.db")},
        "scan": {
            "roots": [str(fixtures_dir)],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": [],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
        "profiles": {},
    }
    with patch("src.cli.load_config", return_value=config):
        runner.invoke(app, ["scan"])
        result = runner.invoke(app, ["diff", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "changes" in data


def test_conflicts_command(tmp_path, fixtures_dir):
    config = {
        "general": {"db_path": str(tmp_path / "test.db")},
        "scan": {
            "roots": [str(fixtures_dir)],
            "extra_paths": [],
            "claude_home": str(tmp_path / "empty_claude"),
            "exclude_patterns": [],
            "file_patterns": ["CLAUDE.md"],
            "memory_pattern": "projects/*/memory/*.md",
            "skill_pattern": "skills/*/SKILL.md",
        },
        "profiles": {},
    }
    with patch("src.cli.load_config", return_value=config):
        runner.invoke(app, ["scan"])
        result = runner.invoke(app, ["conflicts", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "overlaps" in data


def test_config_show_command():
    with patch("src.cli.load_config", return_value={"general": {}, "scan": {}, "profiles": {}}):
        result = runner.invoke(app, ["config", "show", "--json"])
        assert result.exit_code == 0


def test_roots_list_command():
    config = {"general": {}, "scan": {"roots": ["/tmp/test"]}, "profiles": {}}
    with patch("src.cli.load_config", return_value=config):
        result = runner.invoke(app, ["config", "roots", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "/tmp/test" in data["roots"]
