"""Tests for conflicts module."""

from src.conflicts import detect_conflicts
from src.models import Instruction
from src.parsers.claude_md import parse_claude_md


def test_no_conflicts_single_project(storage):
    pid = storage.upsert_project("proj", "/proj")
    fid, _ = storage.upsert_file(pid, "claude-md", "/proj/CLAUDE.md",
                                  "# Test\n\nUse pytest", "h1", 20)
    instructions = [
        Instruction(file_id=fid, section_header="Testing",
                    section_content="Use pytest", topic_keywords="testing",
                    line_start=1, line_end=3),
    ]
    storage.upsert_instructions(fid, instructions)

    result = detect_conflicts(storage)
    assert result.overlaps_found == 0


def test_detects_overlaps(storage):
    pid_a = storage.upsert_project("proj_a", "/proj_a")
    pid_b = storage.upsert_project("proj_b", "/proj_b")
    fid_a, _ = storage.upsert_file(pid_a, "claude-md", "/proj_a/CLAUDE.md",
                                    "# A\n\nUse pytest", "h1", 15)
    fid_b, _ = storage.upsert_file(pid_b, "claude-md", "/proj_b/CLAUDE.md",
                                    "# B\n\nUse pytest too", "h2", 20)

    storage.upsert_instructions(fid_a, [
        Instruction(file_id=fid_a, section_header="Testing",
                    section_content="Use pytest -v", topic_keywords="testing",
                    line_start=1, line_end=3),
    ])
    storage.upsert_instructions(fid_b, [
        Instruction(file_id=fid_b, section_header="Tests",
                    section_content="Use pytest --cov", topic_keywords="testing",
                    line_start=1, line_end=3),
    ])

    result = detect_conflicts(storage)
    assert result.overlaps_found >= 1
    assert any(o.topic == "testing" for o in result.overlaps)


def test_topic_filter(storage):
    pid_a = storage.upsert_project("proj_a", "/proj_a")
    pid_b = storage.upsert_project("proj_b", "/proj_b")
    fid_a, _ = storage.upsert_file(pid_a, "claude-md", "/proj_a/CLAUDE.md",
                                    "content a", "h1", 10)
    fid_b, _ = storage.upsert_file(pid_b, "claude-md", "/proj_b/CLAUDE.md",
                                    "content b", "h2", 10)

    storage.upsert_instructions(fid_a, [
        Instruction(file_id=fid_a, section_header="Testing",
                    section_content="pytest", topic_keywords="testing",
                    line_start=1, line_end=2),
        Instruction(file_id=fid_a, section_header="Git",
                    section_content="git commit", topic_keywords="git",
                    line_start=3, line_end=4),
    ])
    storage.upsert_instructions(fid_b, [
        Instruction(file_id=fid_b, section_header="Tests",
                    section_content="pytest", topic_keywords="testing",
                    line_start=1, line_end=2),
        Instruction(file_id=fid_b, section_header="Git",
                    section_content="git push", topic_keywords="git",
                    line_start=3, line_end=4),
    ])

    result = detect_conflicts(storage, topic_filter="testing")
    assert all(o.topic == "testing" for o in result.overlaps)


def test_conflicts_from_parsed_fixtures(populated_storage, fixtures_dir):
    """Test conflict detection using parsed fixture files."""
    content_a = (fixtures_dir / "project_a" / "CLAUDE.md").read_text()
    content_b = (fixtures_dir / "project_b" / "CLAUDE.md").read_text()

    insts_a = parse_claude_md(content_a)
    insts_b = parse_claude_md(content_b)

    files = populated_storage.get_all_active_files()
    file_a = next(f for f in files if "project_a" in f.file_path)
    file_b = next(f for f in files if "project_b" in f.file_path)

    for inst in insts_a:
        inst.file_id = file_a.id
    for inst in insts_b:
        inst.file_id = file_b.id

    populated_storage.upsert_instructions(file_a.id, insts_a)
    populated_storage.upsert_instructions(file_b.id, insts_b)

    result = detect_conflicts(populated_storage)
    # Both fixtures have "Running Tests" and "Code Style" sections
    assert result.overlaps_found >= 1
