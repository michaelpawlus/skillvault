"""Tests for exporter module."""

import json
import zipfile
import io

import pytest

from src.exporter import export_profile


def test_export_claude_md(populated_storage):
    config = {
        "profiles": {
            "test": {
                "include_patterns": [],
                "project_names": ["project_a", "project_b"],
            },
        },
    }
    result = export_profile(populated_storage, config, "test", fmt="claude-md")
    assert isinstance(result, str)
    assert "Exported Profile: test" in result
    assert "project_a" in result or "project_b" in result


def test_export_archive(populated_storage):
    config = {
        "profiles": {
            "test": {
                "include_patterns": [],
                "project_names": ["project_a", "project_b"],
            },
        },
    }
    result = export_profile(populated_storage, config, "test", fmt="archive")
    assert isinstance(result, bytes)
    zf = zipfile.ZipFile(io.BytesIO(result))
    names = zf.namelist()
    assert "manifest.json" in names
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["profile"] == "test"


def test_export_unknown_profile(populated_storage):
    config = {"profiles": {}}
    with pytest.raises(ValueError, match="not found"):
        export_profile(populated_storage, config, "nonexistent")


def test_export_unknown_format(populated_storage):
    config = {
        "profiles": {
            "test": {"include_patterns": [], "project_names": []},
        },
    }
    with pytest.raises(ValueError, match="Unknown format"):
        export_profile(populated_storage, config, "test", fmt="xml")


def test_export_with_patterns(populated_storage):
    config = {
        "profiles": {
            "test": {
                "include_patterns": ["*PostgreSQL*"],
                "project_names": [],
            },
        },
    }
    result = export_profile(populated_storage, config, "test", fmt="claude-md")
    assert "project_a" in result  # project_a mentions PostgreSQL
