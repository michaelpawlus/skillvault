"""Configuration management for skillvault."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

DEFAULT_CONFIG_PATH = Path("~/.config/skillvault/config.toml").expanduser()
DEFAULT_DB_PATH = Path("~/.local/share/skillvault/skillvault.db").expanduser()

DEFAULT_CONFIG: dict = {
    "general": {
        "db_path": str(DEFAULT_DB_PATH),
        "log_level": "info",
    },
    "scan": {
        "roots": ["~/projects/"],
        "extra_paths": ["~/.claude/CLAUDE.md", "~/.claude/settings.json"],
        "claude_home": "~/.claude",
        "exclude_patterns": ["node_modules", ".venv", "__pycache__", ".git"],
        "file_patterns": ["CLAUDE.md", ".claude/settings.json"],
        "memory_pattern": "projects/*/memory/*.md",
        "skill_pattern": "skills/*/SKILL.md",
    },
    "profiles": {},
}


def load_config(path: Path | None = None) -> dict:
    """Load config from TOML file, creating defaults if missing."""
    config_path = path or DEFAULT_CONFIG_PATH
    if config_path.exists():
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    return DEFAULT_CONFIG.copy()


def save_config(config: dict, path: Path | None = None) -> None:
    """Save config to TOML file."""
    config_path = path or DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)


def get_db_path(config: dict) -> Path:
    """Get the database path from config."""
    raw = config.get("general", {}).get("db_path", str(DEFAULT_DB_PATH))
    return Path(raw).expanduser()


def get_scan_roots(config: dict) -> list[Path]:
    """Get scan root directories from config."""
    roots = config.get("scan", {}).get("roots", ["~/projects/"])
    return [Path(r).expanduser() for r in roots]


def get_extra_paths(config: dict) -> list[Path]:
    """Get extra file paths to scan."""
    paths = config.get("scan", {}).get("extra_paths", [])
    return [Path(p).expanduser() for p in paths]


def get_exclude_patterns(config: dict) -> list[str]:
    """Get directory exclusion patterns."""
    return config.get("scan", {}).get("exclude_patterns", [])


def get_claude_home(config: dict) -> Path:
    """Get the claude home directory."""
    raw = config.get("scan", {}).get("claude_home", "~/.claude")
    return Path(raw).expanduser()


def get_file_patterns(config: dict) -> list[str]:
    """Get file name patterns to match."""
    return config.get("scan", {}).get("file_patterns", ["CLAUDE.md"])


def get_memory_pattern(config: dict) -> str:
    """Get the memory file glob pattern."""
    return config.get("scan", {}).get("memory_pattern", "projects/*/memory/*.md")


def get_skill_pattern(config: dict) -> str:
    """Get the skill file glob pattern."""
    return config.get("scan", {}).get("skill_pattern", "skills/*/SKILL.md")


def get_profiles(config: dict) -> dict:
    """Get all profiles from config."""
    return config.get("profiles", {})


def add_root(config: dict, path: str) -> dict:
    """Add a scan root to config."""
    roots = config.setdefault("scan", {}).setdefault("roots", [])
    if path not in roots:
        roots.append(path)
    return config


def remove_root(config: dict, path: str) -> bool:
    """Remove a scan root from config. Returns True if removed."""
    roots = config.get("scan", {}).get("roots", [])
    if path in roots:
        roots.remove(path)
        return True
    return False


def add_profile(config: dict, name: str, include_patterns: list[str] | None = None,
                project_names: list[str] | None = None) -> dict:
    """Add or update a profile in config."""
    profiles = config.setdefault("profiles", {})
    profiles[name] = {}
    if include_patterns:
        profiles[name]["include_patterns"] = include_patterns
    if project_names:
        profiles[name]["project_names"] = project_names
    return config


def remove_profile(config: dict, name: str) -> bool:
    """Remove a profile from config. Returns True if removed."""
    profiles = config.get("profiles", {})
    if name in profiles:
        del profiles[name]
        return True
    return False
