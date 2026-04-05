"""Tests for storage module."""

import hashlib

from src.models import Instruction
from src.storage import Storage


def test_create_storage(db_path):
    s = Storage(db_path)
    assert db_path.exists()
    s.close()


def test_upsert_project(storage):
    pid = storage.upsert_project("test-project", "/tmp/test")
    assert pid > 0
    # Upserting again returns same id
    pid2 = storage.upsert_project("test-project", "/tmp/test")
    assert pid2 == pid


def test_get_project(storage):
    storage.upsert_project("myproj", "/tmp/myproj")
    proj = storage.get_project("myproj")
    assert proj is not None
    assert proj.name == "myproj"


def test_get_project_not_found(storage):
    assert storage.get_project("nonexistent") is None


def test_list_projects(storage):
    storage.upsert_project("a", "/a")
    storage.upsert_project("b", "/b")
    projects = storage.list_projects()
    assert len(projects) == 2


def test_upsert_file_new(storage):
    pid = storage.upsert_project("proj", "/proj")
    fid, status = storage.upsert_file(pid, "claude-md", "/proj/CLAUDE.md",
                                       "content", "abc123", 7)
    assert status == "new"
    assert fid > 0


def test_upsert_file_unchanged(storage):
    pid = storage.upsert_project("proj", "/proj")
    storage.upsert_file(pid, "claude-md", "/proj/CLAUDE.md", "content", "abc123", 7)
    _, status = storage.upsert_file(pid, "claude-md", "/proj/CLAUDE.md",
                                     "content", "abc123", 7)
    assert status == "unchanged"


def test_upsert_file_changed(storage):
    pid = storage.upsert_project("proj", "/proj")
    storage.upsert_file(pid, "claude-md", "/proj/CLAUDE.md", "content", "abc123", 7)
    _, status = storage.upsert_file(pid, "claude-md", "/proj/CLAUDE.md",
                                     "new content", "def456", 11)
    assert status == "changed"


def test_mark_deleted(storage):
    pid = storage.upsert_project("proj", "/proj")
    storage.upsert_file(pid, "claude-md", "/proj/CLAUDE.md", "content", "abc123", 7)
    assert storage.mark_deleted("/proj/CLAUDE.md") is True
    assert storage.mark_deleted("/proj/CLAUDE.md") is False  # already deleted


def test_get_active_file_paths(storage):
    pid = storage.upsert_project("proj", "/proj")
    storage.upsert_file(pid, "claude-md", "/proj/CLAUDE.md", "content", "abc", 7)
    storage.upsert_file(pid, "memory", "/proj/mem.md", "mem", "def", 3)
    paths = storage.get_active_file_paths()
    assert len(paths) == 2


def test_search_fts(storage):
    pid = storage.upsert_project("proj", "/proj")
    storage.upsert_file(pid, "claude-md", "/proj/CLAUDE.md",
                         "Use pytest for all tests", "hash1", 25)
    results = storage.search("pytest")
    assert len(results) == 1
    assert results[0].project == "proj"


def test_search_with_type_filter(storage):
    pid = storage.upsert_project("proj", "/proj")
    storage.upsert_file(pid, "claude-md", "/proj/CLAUDE.md", "pytest", "h1", 6)
    storage.upsert_file(pid, "memory", "/proj/mem.md", "pytest memory", "h2", 13)
    results = storage.search("pytest", file_type="memory")
    assert len(results) == 1
    assert results[0].file_type == "memory"


def test_record_scan(storage):
    scan_id = storage.record_scan("~/projects", 10, 5, 2, 3, 0, 4, 100)
    assert scan_id > 0
    last = storage.get_last_scan()
    assert last is not None
    assert last["files_found"] == 10


def test_upsert_instructions(storage):
    pid = storage.upsert_project("proj", "/proj")
    fid, _ = storage.upsert_file(pid, "claude-md", "/proj/CLAUDE.md",
                                  "content", "abc", 7)
    instructions = [
        Instruction(file_id=fid, section_header="Testing",
                    section_content="Use pytest", topic_keywords="testing",
                    line_start=1, line_end=3),
    ]
    storage.upsert_instructions(fid, instructions)
    all_inst = storage.get_all_instructions()
    assert len(all_inst) == 1
    assert all_inst[0]["section_header"] == "Testing"


def test_get_all_active_files(storage):
    pid = storage.upsert_project("proj", "/proj")
    storage.upsert_file(pid, "claude-md", "/proj/a.md", "a", "h1", 1)
    storage.upsert_file(pid, "claude-md", "/proj/b.md", "b", "h2", 1)
    storage.mark_deleted("/proj/b.md")
    files = storage.get_all_active_files()
    assert len(files) == 1
