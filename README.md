# skillvault

A cross-project index of every instruction file Claude Code reads — `CLAUDE.md`, `.claude/settings.json`, memory snippets, and installed skills — exposed as a SQLite-backed CLI with full-text search, change tracking, and conflict detection.

## Why

Claude Code's behavior in any given session is the sum of: the global `~/.claude/CLAUDE.md`, the project-local `CLAUDE.md`, per-project memory under `~/.claude/projects/*/memory/`, installed skills under `~/.claude/skills/*/SKILL.md`, and settings files at both levels. Across a portfolio of projects that sprawl grows fast, and answering simple questions becomes hard:

- "Where did I tell Claude to skip mocking the database in tests?"
- "Did this project override the global rule about commit-message style?"
- "What changed in my instructions over the last week?"
- "Give me the curated instruction set I want a new project to start from."

skillvault answers those questions. The CLI builds and maintains the index; an agent (or a human) queries it.

## Install

Requires Python 3.11+.

```bash
git clone https://github.com/michaelpawlus/skillvault
cd skillvault
python -m venv .venv
.venv/bin/pip install -e .[dev]
```

This exposes the `skillvault` entry point. First run scans `~/projects/` plus the global Claude home; configure other roots with `skillvault config roots add PATH`.

## Quick start

```bash
skillvault scan                                  # index everything
skillvault search "database tests"               # FTS5 across all indexed content
skillvault conflicts                             # find overlapping rules across projects
skillvault diff --since 7                        # what changed in the last 7 days
skillvault projects --has CLAUDE.md              # list projects with a CLAUDE.md
skillvault show code-daily                       # dump all indexed files for one project
skillvault export --profile starter              # emit a curated CLAUDE.md
```

Every command supports `--json` for agent orchestration. Human output goes to stderr, JSON to stdout, so commands compose cleanly.

## Commands

| Command | Purpose |
| --- | --- |
| `scan [--root PATH] [--full]` | Discover and index files. Incremental by default; `--full` re-reads everything. |
| `search QUERY [--type] [--project] [--limit]` | FTS5 search across all indexed content. |
| `diff [--since DAYS]` | Show new / modified / deleted files since the last scan (or N days back). |
| `conflicts [--topic TEXT]` | Detect topic overlaps across projects so you can resolve drift between global and project-local rules. |
| `export --profile NAME [--format claude-md\|archive] [--output PATH]` | Emit a curated bundle of instructions matching a profile. |
| `projects [--has TYPE] [--search TEXT]` | List indexed projects, filterable by file type. |
| `show PROJECT [--type TYPE]` | Dump all indexed files for a project. |
| `config show` | Print the active config. |
| `config roots add\|remove\|list PATH` | Manage scan roots. |
| `config profiles add\|remove\|list NAME [--include] [--projects]` | Manage export profiles. |

Run `skillvault COMMAND --help` for full flag reference. Exit codes: `0` ok, `1` error, `2` not-found / validation.

## What gets indexed

| File type | Source pattern |
| --- | --- |
| `CLAUDE.md` | `<root>/**/CLAUDE.md` |
| `settings.json` | `<root>/**/.claude/settings.json`, `~/.claude/settings.json` |
| `memory` | `~/.claude/projects/*/memory/*.md` |
| `skill` | `~/.claude/skills/*/SKILL.md` |

Each file is hashed (SHA-256) on every scan; unchanged files are skipped. Project names are derived from the directory containing the file; skill files are namespaced as `skill:<name>` so they can be queried alongside repos.

## Storage

- Database: `~/.local/share/skillvault/skillvault.db` (SQLite + FTS5).
- Config: `~/.config/skillvault/config.toml`.

Override the DB path via `[general] db_path`, or change scan behavior under `[scan]` (`roots`, `exclude_patterns`, `file_patterns`, `memory_pattern`, `skill_pattern`).

## Profiles

A profile is a named filter used by `export`. It selects which projects and file types to include in a curated bundle:

```bash
skillvault config profiles add starter \
  --include "CLAUDE.md,skill" \
  --projects "code-daily,conductor,agent-ready"

skillvault export --profile starter --output ./STARTER_CLAUDE.md
skillvault export --profile starter --format archive --output ./starter.tar.gz
```

Use this when a new project should inherit a known-good baseline of rules.

## Agent workflows

skillvault collects raw data; the agent (Claude Code in a session) is the intelligence layer. Three workflows the CLI is built around:

**Cross-project instruction audit** — `scan --json` then `conflicts --json`; have Claude Code classify each overlap (conflict vs. override vs. duplication) and write an audit to `$OBSIDIAN_VAULT_PATH/skillvault/audits/{date}.md`.

**New-project bootstrap** — `projects --json` and `search "relevant terms" --json` to surface prior art, then `export --profile NAME` to emit a starter `CLAUDE.md` the agent customizes for the new repo.

**Instruction drift detection** — `diff --json --since 7` weekly; Claude Code categorizes the diff and writes a drift report to `$OBSIDIAN_VAULT_PATH/skillvault/drift/{date}.md`.

Each workflow ends in the Obsidian vault, never in the repo — markdown output convention shared across the portfolio.

## Tests

```bash
.venv/bin/pytest
```

Test suite covers the scanner, storage layer, search/FTS, conflict detection, differ, exporter, config, and CLI surface (`tests/test_*.py`).

## License

MIT.
