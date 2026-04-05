"""CLI entry point for skillvault."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import typer

from .config import (
    add_profile,
    add_root,
    get_db_path,
    get_profiles,
    load_config,
    remove_profile,
    remove_root,
    save_config,
)
from .conflicts import detect_conflicts
from .differ import diff
from .exporter import export_profile
from .models import DiffChange, Overlap
from .scanner import scan
from .storage import Storage

app = typer.Typer(help="CLI index for Claude Code instruction files across projects.")
config_app = typer.Typer(help="Manage skillvault configuration.")
roots_app = typer.Typer(help="Manage scan root directories.")
profiles_app = typer.Typer(help="Manage export profiles.")

app.add_typer(config_app, name="config")
config_app.add_typer(roots_app, name="roots")
config_app.add_typer(profiles_app, name="profiles")


def _get_storage(config: dict | None = None) -> Storage:
    cfg = config or load_config()
    db_path = get_db_path(cfg)
    return Storage(db_path)


def _output_json(data: dict) -> None:
    """Print JSON to stdout."""
    typer.echo(json.dumps(data, indent=2, default=str))


def _output_human(msg: str) -> None:
    """Print human-readable message to stderr."""
    print(msg, file=sys.stderr)


# -- scan --

@app.command(name="scan")
def scan_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
    root: Optional[str] = typer.Option(None, "--root", help="Override: scan only this root"),
    full: bool = typer.Option(False, "--full", help="Force full re-index"),
) -> None:
    """Discover and index all instruction files."""
    config = load_config()
    storage = _get_storage(config)
    try:
        result = scan(storage, config, root_override=root, full=full)
        if json_output:
            _output_json(asdict(result))
        else:
            _output_human(
                f"Scan complete: {result.files_found} files found "
                f"({result.new} new, {result.changed} changed, "
                f"{result.unchanged} unchanged, {result.deleted} deleted) "
                f"across {result.projects_discovered} projects "
                f"in {result.duration_ms}ms"
            )
    finally:
        storage.close()


# -- search --

@app.command()
def search(
    query: str = typer.Argument(..., help="Search terms (FTS5 syntax)"),
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
    type: Optional[str] = typer.Option(None, "--type", help="Filter by file type"),
    project: Optional[str] = typer.Option(None, "--project", help="Limit to project"),
    limit: int = typer.Option(20, "--limit", help="Max results"),
) -> None:
    """Full-text search across indexed content."""
    storage = _get_storage()
    try:
        results = storage.search(query, file_type=type, project_name=project, limit=limit)
        if json_output:
            _output_json({
                "query": query,
                "total_matches": len(results),
                "results": [asdict(r) for r in results],
            })
        else:
            if not results:
                _output_human(f"No results for '{query}'")
                return
            for r in results:
                _output_human(f"[{r.project}] {r.file_type} — {r.file_path}")
                _output_human(f"  {r.snippet}")
                _output_human("")
    finally:
        storage.close()


# -- diff --

@app.command(name="diff")
def diff_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
    since: Optional[int] = typer.Option(None, "--since", help="Days to look back"),
) -> None:
    """Show what changed since the last scan."""
    storage = _get_storage()
    try:
        result = diff(storage, since_days=since)
        if json_output:
            data = {
                "since": result.since,
                "changes": {
                    k: [asdict(c) for c in v]
                    for k, v in result.changes.items()
                },
                "summary": result.summary,
            }
            _output_json(data)
        else:
            total = sum(result.summary.values())
            if total == 0:
                _output_human("No changes detected.")
                return
            _output_human(f"Changes since {result.since}:")
            for change_type, items in result.changes.items():
                for item in items:
                    _output_human(f"  [{change_type}] {item.project}: {item.path}")
                    if item.diff:
                        for line in item.diff.split("\n")[:10]:
                            _output_human(f"    {line}")
            _output_human(
                f"\nSummary: {result.summary['new']} new, "
                f"{result.summary['modified']} modified, "
                f"{result.summary['deleted']} deleted"
            )
    finally:
        storage.close()


# -- conflicts --

@app.command()
def conflicts(
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
    topic: Optional[str] = typer.Option(None, "--topic", help="Filter by topic"),
) -> None:
    """Detect overlapping instructions across projects."""
    storage = _get_storage()
    try:
        result = detect_conflicts(storage, topic_filter=topic)
        if json_output:
            data = {
                "topics_analyzed": result.topics_analyzed,
                "overlaps_found": result.overlaps_found,
                "overlaps": [
                    {
                        "topic": o.topic,
                        "keyword_matches": o.keyword_matches,
                        "instructions": o.instructions,
                    }
                    for o in result.overlaps
                ],
            }
            _output_json(data)
        else:
            if result.overlaps_found == 0:
                _output_human(f"No overlaps found across {result.topics_analyzed} topics.")
                return
            _output_human(
                f"Found {result.overlaps_found} overlaps "
                f"across {result.topics_analyzed} topics:\n"
            )
            for overlap in result.overlaps:
                _output_human(f"  Topic: {overlap.topic}")
                _output_human(f"  Keywords: {', '.join(overlap.keyword_matches)}")
                for inst in overlap.instructions:
                    _output_human(f"    [{inst['project']}] {inst['section']} — {inst['file']}")
                _output_human("")
    finally:
        storage.close()


# -- export --

@app.command(name="export")
def export_cmd(
    profile_name: str = typer.Option(..., "--profile", help="Profile name to export"),
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
    format: str = typer.Option("claude-md", "--format", help="Output format: claude-md or archive"),
    output: Optional[str] = typer.Option(None, "--output", help="Write to file path"),
) -> None:
    """Export a curated profile of instructions."""
    config = load_config()
    storage = _get_storage(config)
    try:
        result = export_profile(storage, config, profile_name, fmt=format)
        if format == "archive":
            if output:
                Path(output).write_bytes(result)  # type: ignore[arg-type]
                if json_output:
                    _output_json({"status": "ok", "path": output, "format": "archive"})
                else:
                    _output_human(f"Archive written to {output}")
            else:
                _output_human("Archive format requires --output PATH")
                raise typer.Exit(code=1)
        else:
            if output:
                Path(output).write_text(result)  # type: ignore[arg-type]
                if json_output:
                    _output_json({"status": "ok", "path": output, "format": "claude-md"})
                else:
                    _output_human(f"Exported to {output}")
            else:
                if json_output:
                    _output_json({"status": "ok", "content": result, "format": "claude-md"})
                else:
                    typer.echo(result)
    except ValueError as e:
        if json_output:
            _output_json({"error": str(e), "code": 2})
        else:
            _output_human(f"Error: {e}")
        raise typer.Exit(code=2)
    finally:
        storage.close()


# -- projects --

@app.command()
def projects(
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
    has: Optional[str] = typer.Option(None, "--has", help="Filter by file type"),
    search_text: Optional[str] = typer.Option(None, "--search", help="Search project names"),
) -> None:
    """List all discovered projects."""
    storage = _get_storage()
    try:
        project_list = storage.list_projects(has_type=has, search=search_text)
        if json_output:
            _output_json({
                "total": len(project_list),
                "projects": [asdict(p) for p in project_list],
            })
        else:
            if not project_list:
                _output_human("No projects found. Run 'skillvault scan' first.")
                return
            for p in project_list:
                _output_human(f"  {p.name} — {p.path}")
    finally:
        storage.close()


# -- show --

@app.command()
def show(
    project_name: str = typer.Argument(..., help="Project name to display"),
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
    type: Optional[str] = typer.Option(None, "--type", help="Filter by file type"),
) -> None:
    """Display indexed content for a project."""
    storage = _get_storage()
    try:
        project = storage.get_project(project_name)
        if not project:
            if json_output:
                _output_json({"error": f"Project '{project_name}' not found", "code": 2})
            else:
                _output_human(f"Project '{project_name}' not found")
            raise typer.Exit(code=2)

        files = storage.get_files_by_project(project.id, file_type=type)  # type: ignore[arg-type]
        if json_output:
            _output_json({
                "project": asdict(project),
                "files": [asdict(f) for f in files],
            })
        else:
            _output_human(f"Project: {project.name} ({project.path})\n")
            for f in files:
                _output_human(f"--- {f.file_type}: {f.file_path} ---")
                _output_human(f.content)
                _output_human("")
    finally:
        storage.close()


# -- config show --

@config_app.command(name="show")
def config_show(
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
) -> None:
    """Show current configuration."""
    config = load_config()
    if json_output:
        _output_json(config)
    else:
        _output_human(json.dumps(config, indent=2))


# -- config roots --

@roots_app.command(name="list")
def roots_list(
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
) -> None:
    """List configured scan roots."""
    config = load_config()
    roots = config.get("scan", {}).get("roots", [])
    if json_output:
        _output_json({"roots": roots})
    else:
        for r in roots:
            _output_human(f"  {r}")


@roots_app.command(name="add")
def roots_add(
    path: str = typer.Argument(..., help="Root path to add"),
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
) -> None:
    """Add a scan root directory."""
    config = load_config()
    add_root(config, path)
    save_config(config)
    if json_output:
        _output_json({"status": "ok", "roots": config["scan"]["roots"]})
    else:
        _output_human(f"Added root: {path}")


@roots_app.command(name="remove")
def roots_remove(
    path: str = typer.Argument(..., help="Root path to remove"),
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
) -> None:
    """Remove a scan root directory."""
    config = load_config()
    if remove_root(config, path):
        save_config(config)
        if json_output:
            _output_json({"status": "ok", "roots": config["scan"]["roots"]})
        else:
            _output_human(f"Removed root: {path}")
    else:
        if json_output:
            _output_json({"error": f"Root '{path}' not found", "code": 2})
        else:
            _output_human(f"Root '{path}' not found")
        raise typer.Exit(code=2)


# -- config profiles --

@profiles_app.command(name="list")
def profiles_list(
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
) -> None:
    """List configured profiles."""
    config = load_config()
    profs = get_profiles(config)
    if json_output:
        _output_json({"profiles": profs})
    else:
        if not profs:
            _output_human("No profiles configured.")
            return
        for name, details in profs.items():
            _output_human(f"  {name}: {details}")


@profiles_app.command(name="add")
def profiles_add(
    name: str = typer.Argument(..., help="Profile name"),
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
    include: Optional[str] = typer.Option(None, "--include", help="Comma-separated include patterns"),
    projects_opt: Optional[str] = typer.Option(None, "--projects", help="Comma-separated project names"),
) -> None:
    """Add or update an export profile."""
    config = load_config()
    patterns = [p.strip() for p in include.split(",")] if include else None
    proj_names = [p.strip() for p in projects_opt.split(",")] if projects_opt else None
    add_profile(config, name, include_patterns=patterns, project_names=proj_names)
    save_config(config)
    if json_output:
        _output_json({"status": "ok", "profile": name})
    else:
        _output_human(f"Profile '{name}' saved.")


@profiles_app.command(name="remove")
def profiles_remove(
    name: str = typer.Argument(..., help="Profile name to remove"),
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON"),
) -> None:
    """Remove an export profile."""
    config = load_config()
    if remove_profile(config, name):
        save_config(config)
        if json_output:
            _output_json({"status": "ok", "removed": name})
        else:
            _output_human(f"Profile '{name}' removed.")
    else:
        if json_output:
            _output_json({"error": f"Profile '{name}' not found", "code": 2})
        else:
            _output_human(f"Profile '{name}' not found")
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
