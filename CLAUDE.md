# Claude Code Notes

## Running Tests

    .venv/bin/pytest

## CLI Commands

    skillvault scan [--json] [--root PATH] [--full]
    skillvault search QUERY [--json] [--type TYPE] [--project NAME] [--limit INT]
    skillvault diff [--json] [--since DAYS]
    skillvault conflicts [--json] [--topic TEXT]
    skillvault export --profile NAME [--json] [--format FORMAT] [--output PATH]
    skillvault projects [--json] [--has TYPE] [--search TEXT]
    skillvault show PROJECT [--json] [--type TYPE]
    skillvault config roots list|add|remove [--json]
    skillvault config profiles list|add|remove [--json]
    skillvault config show [--json]

All commands support `--json` for agent orchestration (JSON to stdout, human text to stderr).

## Database

SQLite at `~/.local/share/skillvault/skillvault.db` with FTS5.
Config at `~/.config/skillvault/config.toml`.

## Agent Persona

skillvault is a tool for the agent. Claude Code uses skillvault to:
- Search across all project instructions before starting work
- Detect conflicts between global and project-level rules
- Export curated instruction sets for new projects
- Track how instructions evolve over time

The CLI indexes raw data. Claude Code is the intelligence layer.

## Agent Workflow: Cross-Project Instruction Audit

1. `skillvault scan --json`
2. `skillvault conflicts --json`
3. Claude Code classifies each overlap (conflict / override / duplication)
4. Write audit to `$OBSIDIAN_VAULT_PATH/skillvault/audits/{date}.md`

## Agent Workflow: New Project Bootstrap

1. `skillvault projects --json`
2. `skillvault search "relevant terms" --json`
3. `skillvault export --profile NAME --json`
4. Claude Code customizes for the new project

## Agent Workflow: Instruction Drift Detection

1. `skillvault diff --json --since 7`
2. Claude Code categorizes changes
3. Write drift report to `$OBSIDIAN_VAULT_PATH/skillvault/drift/{date}.md`

## Vault Output

Markdown output goes to `$OBSIDIAN_VAULT_PATH/skillvault/`.
Subfolders: `audits/`, `drift/`, `exports/`.
