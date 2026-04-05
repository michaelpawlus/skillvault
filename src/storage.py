"""SQLite storage layer with FTS5 for skillvault."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import get_db_path
from .models import FileRecord, Instruction, Profile, Project, SearchResult

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    path TEXT UNIQUE NOT NULL,
    discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_scanned_at TEXT,
    is_active INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    file_type TEXT NOT NULL CHECK(file_type IN ('claude-md', 'memory', 'skill', 'settings')),
    file_path TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    first_indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_files_project ON files(project_id);
CREATE INDEX IF NOT EXISTS idx_files_type ON files(file_type);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path);

CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,
    roots_scanned TEXT NOT NULL,
    files_found INTEGER NOT NULL,
    files_new INTEGER NOT NULL,
    files_changed INTEGER NOT NULL,
    files_unchanged INTEGER NOT NULL,
    files_deleted INTEGER NOT NULL,
    projects_discovered INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    include_patterns TEXT,
    project_names TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS instructions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(id),
    section_header TEXT NOT NULL,
    section_content TEXT NOT NULL,
    topic_keywords TEXT,
    line_start INTEGER,
    line_end INTEGER
);

CREATE INDEX IF NOT EXISTS idx_instructions_file ON instructions(file_id);
CREATE INDEX IF NOT EXISTS idx_instructions_topic ON instructions(topic_keywords);
"""

FTS_SETUP_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
    content,
    project_name,
    file_type,
    file_path,
    tokenize='porter unicode61'
);
"""

FTS_TRIGGERS_SQL = ""  # FTS is managed manually in Python for reliability


class Storage:
    """SQLite database interface for skillvault."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables, FTS, and triggers if they don't exist."""
        self.conn.executescript(SCHEMA_SQL)
        self.conn.executescript(FTS_SETUP_SQL)
        self.conn.executescript(FTS_TRIGGERS_SQL)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- Projects --

    def upsert_project(self, name: str, path: str) -> int:
        """Insert or get existing project. Returns project id."""
        row = self.conn.execute(
            "SELECT id FROM projects WHERE name = ?", (name,)
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE projects SET last_scanned_at = CURRENT_TIMESTAMP, is_active = 1 WHERE id = ?",
                (row["id"],),
            )
            self.conn.commit()
            return row["id"]
        cur = self.conn.execute(
            "INSERT INTO projects (name, path) VALUES (?, ?)", (name, path)
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_project(self, name: str) -> Project | None:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            return None
        return Project(
            id=row["id"], name=row["name"], path=row["path"],
            discovered_at=row["discovered_at"],
            last_scanned_at=row["last_scanned_at"],
            is_active=bool(row["is_active"]),
        )

    def list_projects(self, has_type: str | None = None, search: str | None = None) -> list[Project]:
        query = "SELECT DISTINCT p.* FROM projects p"
        conditions = ["p.is_active = 1"]
        params: list = []
        if has_type:
            query += " JOIN files f ON f.project_id = p.id"
            conditions.append("f.file_type = ?")
            conditions.append("f.is_deleted = 0")
            params.append(has_type)
        if search:
            conditions.append("p.name LIKE ?")
            params.append(f"%{search}%")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY p.name"
        rows = self.conn.execute(query, params).fetchall()
        return [
            Project(id=r["id"], name=r["name"], path=r["path"],
                    discovered_at=r["discovered_at"],
                    last_scanned_at=r["last_scanned_at"],
                    is_active=bool(r["is_active"]))
            for r in rows
        ]

    # -- Files --

    def get_file_by_path(self, file_path: str) -> FileRecord | None:
        row = self.conn.execute(
            "SELECT * FROM files WHERE file_path = ?", (file_path,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_file(row)

    def get_files_by_project(self, project_id: int, file_type: str | None = None) -> list[FileRecord]:
        query = "SELECT * FROM files WHERE project_id = ? AND is_deleted = 0"
        params: list = [project_id]
        if file_type:
            query += " AND file_type = ?"
            params.append(file_type)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_file(r) for r in rows]

    def upsert_file(self, project_id: int, file_type: str, file_path: str,
                    content: str, content_hash: str, size_bytes: int) -> tuple[int, str]:
        """Insert or update a file. Returns (file_id, status) where status is 'new', 'changed', or 'unchanged'."""
        project_name = self._project_name_by_id(project_id)
        existing = self.conn.execute(
            "SELECT id, content_hash, is_deleted FROM files WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        if existing:
            fid = existing["id"]
            if existing["is_deleted"]:
                self.conn.execute(
                    """UPDATE files SET content = ?, content_hash = ?, size_bytes = ?,
                       last_indexed_at = CURRENT_TIMESTAMP, is_deleted = 0, project_id = ?,
                       file_type = ?
                       WHERE id = ?""",
                    (content, content_hash, size_bytes, project_id, file_type, fid),
                )
                self._fts_insert(fid, content, project_name, file_type, file_path)
                self.conn.commit()
                return fid, "new"
            if existing["content_hash"] == content_hash:
                self.conn.execute(
                    "UPDATE files SET last_indexed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (fid,),
                )
                self.conn.commit()
                return fid, "unchanged"
            # Changed — delete old FTS entry, update row, insert new FTS entry
            self._fts_delete(fid)
            self.conn.execute(
                """UPDATE files SET content = ?, content_hash = ?, size_bytes = ?,
                   last_indexed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (content, content_hash, size_bytes, fid),
            )
            self._fts_insert(fid, content, project_name, file_type, file_path)
            self.conn.commit()
            return fid, "changed"
        cur = self.conn.execute(
            """INSERT INTO files (project_id, file_type, file_path, content, content_hash, size_bytes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, file_type, file_path, content, content_hash, size_bytes),
        )
        fid = cur.lastrowid
        self._fts_insert(fid, content, project_name, file_type, file_path)
        self.conn.commit()
        return fid, "new"  # type: ignore[return-value]

    def _fts_insert(self, rowid: int, content: str, project_name: str,
                    file_type: str, file_path: str) -> None:
        self.conn.execute(
            "INSERT INTO files_fts(rowid, content, project_name, file_type, file_path) VALUES (?, ?, ?, ?, ?)",
            (rowid, content, project_name, file_type, file_path),
        )

    def _fts_delete(self, rowid: int) -> None:
        """Remove an FTS entry by rowid."""
        self.conn.execute("DELETE FROM files_fts WHERE rowid = ?", (rowid,))

    def _project_name_by_id(self, project_id: int) -> str:
        row = self.conn.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
        return row["name"] if row else "unknown"

    def mark_deleted(self, file_path: str) -> bool:
        """Mark a file as deleted. Returns True if it was active."""
        cur = self.conn.execute(
            "UPDATE files SET is_deleted = 1 WHERE file_path = ? AND is_deleted = 0",
            (file_path,),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_active_file_paths(self) -> set[str]:
        """Get all non-deleted file paths."""
        rows = self.conn.execute(
            "SELECT file_path FROM files WHERE is_deleted = 0"
        ).fetchall()
        return {r["file_path"] for r in rows}

    def _row_to_file(self, row: sqlite3.Row) -> FileRecord:
        return FileRecord(
            id=row["id"], project_id=row["project_id"],
            file_type=row["file_type"], file_path=row["file_path"],
            content=row["content"], content_hash=row["content_hash"],
            size_bytes=row["size_bytes"],
            first_indexed_at=row["first_indexed_at"],
            last_indexed_at=row["last_indexed_at"],
            is_deleted=bool(row["is_deleted"]),
        )

    # -- Search --

    def search(self, query: str, file_type: str | None = None,
               project_name: str | None = None, limit: int = 20) -> list[SearchResult]:
        """Full-text search across indexed files."""
        fts_query = query
        conditions = ["files_fts MATCH ?"]
        params: list = [fts_query]
        if file_type:
            conditions.append("file_type = ?")
            params.append(file_type)
        if project_name:
            conditions.append("project_name = ?")
            params.append(project_name)
        where = " AND ".join(conditions)
        params.append(limit)
        sql = f"""
            SELECT rowid, project_name, file_type, file_path,
                   snippet(files_fts, 0, '', '', '...', 40) as snippet,
                   rank
            FROM files_fts
            WHERE {where}
            ORDER BY rank
            LIMIT ?
        """
        rows = self.conn.execute(sql, params).fetchall()
        results = []
        for r in rows:
            file_row = self.conn.execute(
                "SELECT last_indexed_at FROM files WHERE id = ?", (r["rowid"],)
            ).fetchone()
            last_scanned = file_row["last_indexed_at"] if file_row else ""
            results.append(SearchResult(
                file_id=r["rowid"], project=r["project_name"],
                file_type=r["file_type"], file_path=r["file_path"],
                snippet=r["snippet"], rank=r["rank"],
                last_scanned=last_scanned,
            ))
        return results

    # -- Scan History --

    def record_scan(self, roots_scanned: str, files_found: int, files_new: int,
                    files_changed: int, files_unchanged: int, files_deleted: int,
                    projects_discovered: int, duration_ms: int) -> int:
        cur = self.conn.execute(
            """INSERT INTO scan_history
               (roots_scanned, files_found, files_new, files_changed,
                files_unchanged, files_deleted, projects_discovered, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (roots_scanned, files_found, files_new, files_changed,
             files_unchanged, files_deleted, projects_discovered, duration_ms),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_last_scan(self) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM scan_history ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return dict(row)

    # -- Instructions --

    def upsert_instructions(self, file_id: int, instructions: list[Instruction]) -> None:
        """Replace all instructions for a file."""
        self.conn.execute("DELETE FROM instructions WHERE file_id = ?", (file_id,))
        for inst in instructions:
            self.conn.execute(
                """INSERT INTO instructions (file_id, section_header, section_content,
                   topic_keywords, line_start, line_end)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (file_id, inst.section_header, inst.section_content,
                 inst.topic_keywords, inst.line_start, inst.line_end),
            )
        self.conn.commit()

    def get_all_instructions(self) -> list[dict]:
        """Get all instructions joined with file and project info."""
        rows = self.conn.execute("""
            SELECT i.*, f.file_path, f.file_type, p.name as project_name
            FROM instructions i
            JOIN files f ON f.id = i.file_id
            JOIN projects p ON p.id = f.project_id
            WHERE f.is_deleted = 0
        """).fetchall()
        return [dict(r) for r in rows]

    # -- Files for diff --

    def get_files_indexed_since(self, since: str) -> list[FileRecord]:
        """Get files that were indexed after a given timestamp."""
        rows = self.conn.execute(
            "SELECT * FROM files WHERE last_indexed_at >= ?", (since,)
        ).fetchall()
        return [self._row_to_file(r) for r in rows]

    def get_all_active_files(self) -> list[FileRecord]:
        """Get all non-deleted files."""
        rows = self.conn.execute(
            "SELECT * FROM files WHERE is_deleted = 0"
        ).fetchall()
        return [self._row_to_file(r) for r in rows]
