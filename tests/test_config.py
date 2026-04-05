"""Tests for config module."""

from pathlib import Path

from src.config import (
    add_profile,
    add_root,
    get_db_path,
    get_profiles,
    get_scan_roots,
    load_config,
    remove_profile,
    remove_root,
    save_config,
)


def test_load_config_defaults():
    config = load_config(Path("/nonexistent/config.toml"))
    assert "general" in config
    assert "scan" in config
    assert "profiles" in config


def test_save_and_load_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config = {"general": {"db_path": "/tmp/test.db"}, "scan": {"roots": ["/tmp"]}, "profiles": {}}
    save_config(config, config_path)
    loaded = load_config(config_path)
    assert loaded["general"]["db_path"] == "/tmp/test.db"


def test_get_db_path():
    config = {"general": {"db_path": "/tmp/test.db"}}
    assert get_db_path(config) == Path("/tmp/test.db")


def test_get_scan_roots():
    config = {"scan": {"roots": ["/tmp/projects"]}}
    roots = get_scan_roots(config)
    assert len(roots) == 1
    assert roots[0] == Path("/tmp/projects")


def test_add_root():
    config = {"scan": {"roots": ["/existing"]}}
    add_root(config, "/new")
    assert "/new" in config["scan"]["roots"]


def test_add_root_no_duplicate():
    config = {"scan": {"roots": ["/existing"]}}
    add_root(config, "/existing")
    assert config["scan"]["roots"].count("/existing") == 1


def test_remove_root():
    config = {"scan": {"roots": ["/a", "/b"]}}
    assert remove_root(config, "/a") is True
    assert "/a" not in config["scan"]["roots"]


def test_remove_root_missing():
    config = {"scan": {"roots": ["/a"]}}
    assert remove_root(config, "/missing") is False


def test_add_profile():
    config = {"profiles": {}}
    add_profile(config, "test", include_patterns=["*test*"], project_names=["proj1"])
    assert "test" in config["profiles"]
    assert config["profiles"]["test"]["include_patterns"] == ["*test*"]


def test_remove_profile():
    config = {"profiles": {"test": {"include_patterns": []}}}
    assert remove_profile(config, "test") is True
    assert "test" not in config["profiles"]


def test_remove_profile_missing():
    config = {"profiles": {}}
    assert remove_profile(config, "missing") is False


def test_get_profiles():
    config = {"profiles": {"a": {}, "b": {}}}
    assert len(get_profiles(config)) == 2
