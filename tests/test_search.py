"""Tests for search functionality."""


def test_search_returns_results(populated_storage):
    results = populated_storage.search("pytest")
    assert len(results) >= 1


def test_search_project_filter(populated_storage):
    results = populated_storage.search("pytest", project_name="project_a")
    assert all(r.project == "project_a" for r in results)


def test_search_type_filter(populated_storage):
    results = populated_storage.search("Tests", file_type="claude-md")
    assert all(r.file_type == "claude-md" for r in results)


def test_search_no_results(populated_storage):
    results = populated_storage.search("xyznonexistent")
    assert len(results) == 0


def test_search_limit(populated_storage):
    results = populated_storage.search("Project", limit=1)
    assert len(results) <= 1
