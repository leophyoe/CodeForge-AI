from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

from .models import (
    Dependency,
    FileRecord,
    FileStatus,
    ImportReference,
    IndexJob,
    IndexStatus,
    JobStatus,
    Symbol,
    SymbolKind,
    Workspace,
)

if TYPE_CHECKING:
    from pathlib import Path


class Storage:
    def __init__(self, db_path: str | Path = "codeforge_index.db") -> None:
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                workspace_id TEXT PRIMARY KEY,
                root_path TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                index_status TEXT NOT NULL DEFAULT 'NOT_INDEXED'
            );

            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                mtime REAL NOT NULL DEFAULT 0.0,
                content_hash TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'DISCOVERED',
                symbol_count INTEGER NOT NULL DEFAULT 0,
                parse_status TEXT NOT NULL DEFAULT 'OK',
                is_binary INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_files_workspace ON files(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_files_path ON files(relative_path);
            CREATE INDEX IF NOT EXISTS idx_files_language ON files(language);

            CREATE TABLE IF NOT EXISTS symbols (
                symbol_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT '',
                start_line INTEGER NOT NULL DEFAULT 0,
                start_column INTEGER NOT NULL DEFAULT 0,
                end_line INTEGER NOT NULL DEFAULT 0,
                end_column INTEGER NOT NULL DEFAULT 0,
                parent_symbol_id TEXT NOT NULL DEFAULT '',
                visibility TEXT NOT NULL DEFAULT '',
                signature TEXT NOT NULL DEFAULT '',
                documentation TEXT NOT NULL DEFAULT '',
                qualified_name TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_symbols_workspace ON symbols(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);
            CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
            CREATE INDEX IF NOT EXISTS idx_symbols_qualified ON symbols(qualified_name);
            CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);

            CREATE TABLE IF NOT EXISTS imports (
                import_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                import_path TEXT NOT NULL,
                import_kind TEXT NOT NULL,
                imported_names TEXT NOT NULL DEFAULT '[]',
                line INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_imports_workspace ON imports(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_imports_file ON imports(file_id);

            CREATE TABLE IF NOT EXISTS exports (
                export_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                export_name TEXT NOT NULL,
                symbol_id TEXT NOT NULL DEFAULT '',
                line INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_exports_workspace ON exports(workspace_id);

            CREATE TABLE IF NOT EXISTS dependencies (
                dependency_id TEXT PRIMARY KEY,
                source_file_id TEXT NOT NULL,
                target_file_id TEXT NOT NULL DEFAULT '',
                workspace_id TEXT NOT NULL,
                import_path TEXT NOT NULL,
                resolved INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (source_file_id) REFERENCES files(file_id) ON DELETE CASCADE,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_deps_workspace ON dependencies(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_deps_source ON dependencies(source_file_id);

            CREATE TABLE IF NOT EXISTS index_jobs (
                job_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'QUEUED',
                files_total INTEGER NOT NULL DEFAULT 0,
                files_processed INTEGER NOT NULL DEFAULT 0,
                files_failed INTEGER NOT NULL DEFAULT 0,
                symbols_extracted INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                started_at REAL NOT NULL DEFAULT 0.0,
                completed_at REAL NOT NULL DEFAULT 0.0,
                error_message TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()

    def save_workspace(self, ws: Workspace) -> None:
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT workspace_id FROM workspaces WHERE workspace_id = ?",
            (ws.workspace_id,),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE workspaces SET root_path = ?, name = ?, updated_at = ?, index_status = ?
                   WHERE workspace_id = ?""",
                (ws.root_path, ws.name, ws.updated_at, ws.index_status.value, ws.workspace_id),
            )
        else:
            conn.execute(
                """INSERT INTO workspaces
                   (workspace_id, root_path, name, created_at, updated_at, index_status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    ws.workspace_id,
                    ws.root_path,
                    ws.name,
                    ws.created_at,
                    ws.updated_at,
                    ws.index_status.value,
                ),
            )
        conn.commit()

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()
        if not row:
            return None
        return Workspace(
            workspace_id=row["workspace_id"],
            root_path=row["root_path"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            index_status=IndexStatus(row["index_status"]),
        )

    def list_workspaces(self) -> list[Workspace]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM workspaces ORDER BY created_at DESC").fetchall()
        return [
            Workspace(
                workspace_id=r["workspace_id"],
                root_path=r["root_path"],
                name=r["name"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                index_status=IndexStatus(r["index_status"]),
            )
            for r in rows
        ]

    def delete_workspace(self, workspace_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM workspaces WHERE workspace_id = ?", (workspace_id,))
        conn.commit()
        return cursor.rowcount > 0

    def save_file(self, f: FileRecord) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO files
               (file_id, workspace_id, relative_path, language, size, mtime,
                content_hash, status, symbol_count, parse_status, is_binary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f.file_id,
                f.workspace_id,
                f.relative_path,
                f.language,
                f.size,
                f.mtime,
                f.content_hash,
                f.status.value,
                f.symbol_count,
                f.parse_status,
                1 if f.is_binary else 0,
            ),
        )
        conn.commit()

    def save_files(self, files: list[FileRecord]) -> None:
        conn = self._get_conn()
        conn.executemany(
            """INSERT OR REPLACE INTO files
               (file_id, workspace_id, relative_path, language, size, mtime,
                content_hash, status, symbol_count, parse_status, is_binary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    f.file_id,
                    f.workspace_id,
                    f.relative_path,
                    f.language,
                    f.size,
                    f.mtime,
                    f.content_hash,
                    f.status.value,
                    f.symbol_count,
                    f.parse_status,
                    1 if f.is_binary else 0,
                )
                for f in files
            ],
        )
        conn.commit()

    def get_file(self, file_id: str) -> FileRecord | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM files WHERE file_id = ?", (file_id,)).fetchone()
        if not row:
            return None
        return self._row_to_file(row)

    def get_file_by_path(self, workspace_id: str, relative_path: str) -> FileRecord | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM files WHERE workspace_id = ? AND relative_path = ?",
            (workspace_id, relative_path),
        ).fetchone()
        if not row:
            return None
        return self._row_to_file(row)

    def get_workspace_files(self, workspace_id: str) -> list[FileRecord]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM files WHERE workspace_id = ? ORDER BY relative_path",
            (workspace_id,),
        ).fetchall()
        return [self._row_to_file(r) for r in rows]

    def delete_file(self, file_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
        conn.commit()
        return cursor.rowcount > 0

    def delete_workspace_files(self, workspace_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM files WHERE workspace_id = ?", (workspace_id,))
        conn.commit()

    def save_symbols(self, symbols: list[Symbol]) -> None:
        conn = self._get_conn()
        conn.executemany(
            """INSERT OR REPLACE INTO symbols
               (symbol_id, file_id, workspace_id, name, kind, language,
                start_line, start_column, end_line, end_column,
                parent_symbol_id, visibility, signature, documentation, qualified_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    s.symbol_id,
                    s.file_id,
                    s.workspace_id,
                    s.name,
                    s.kind.value,
                    s.language,
                    s.start_line,
                    s.start_column,
                    s.end_line,
                    s.end_column,
                    s.parent_symbol_id,
                    s.visibility,
                    s.signature,
                    s.documentation,
                    s.qualified_name,
                )
                for s in symbols
            ],
        )
        conn.commit()

    def get_file_symbols(self, file_id: str) -> list[Symbol]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM symbols WHERE file_id = ? ORDER BY start_line", (file_id,)
        ).fetchall()
        return [self._row_to_symbol(r) for r in rows]

    def get_workspace_symbols(self, workspace_id: str) -> list[Symbol]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM symbols WHERE workspace_id = ? ORDER BY name", (workspace_id,)
        ).fetchall()
        return [self._row_to_symbol(r) for r in rows]

    def find_symbols(
        self,
        workspace_id: str,
        name: str | None = None,
        kind: SymbolKind | None = None,
        qualified_name: str | None = None,
    ) -> list[Symbol]:
        conn = self._get_conn()
        conditions = ["workspace_id = ?"]
        params: list = [workspace_id]
        if name:
            conditions.append("name = ?")
            params.append(name)
        if kind:
            conditions.append("kind = ?")
            params.append(kind.value)
        if qualified_name:
            conditions.append("qualified_name = ?")
            params.append(qualified_name)
        where = " AND ".join(conditions)
        # `where` contains only internal literals; values use ? placeholders.
        rows = conn.execute(
            f"SELECT * FROM symbols WHERE {where} ORDER BY name",  # noqa: S608
            params,
        ).fetchall()
        return [self._row_to_symbol(r) for r in rows]

    def delete_file_symbols(self, file_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
        conn.commit()

    def save_imports(self, imports: list[ImportReference]) -> None:
        conn = self._get_conn()
        conn.executemany(
            """INSERT OR REPLACE INTO imports
               (import_id, file_id, workspace_id, import_path, import_kind,
                imported_names, line)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    imp.import_id,
                    imp.file_id,
                    imp.workspace_id,
                    imp.import_path,
                    imp.import_kind.value,
                    json.dumps(imp.imported_names),
                    imp.line,
                )
                for imp in imports
            ],
        )
        conn.commit()

    def get_file_imports(self, file_id: str) -> list[ImportReference]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM imports WHERE file_id = ? ORDER BY line", (file_id,)
        ).fetchall()
        return [self._row_to_import(r) for r in rows]

    def delete_file_imports(self, file_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM imports WHERE file_id = ?", (file_id,))
        conn.commit()

    def save_exports(self, exports: list[dict]) -> None:
        conn = self._get_conn()
        conn.executemany(
            """INSERT OR REPLACE INTO exports
               (export_id, file_id, workspace_id, export_name, symbol_id, line)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (
                    e.get("export_id", ""),
                    e.get("file_id", ""),
                    e.get("workspace_id", ""),
                    e.get("export_name", ""),
                    e.get("symbol_id", ""),
                    e.get("line", 0),
                )
                for e in exports
            ],
        )
        conn.commit()

    def delete_file_exports(self, file_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM exports WHERE file_id = ?", (file_id,))
        conn.commit()

    def save_dependencies(self, deps: list[Dependency]) -> None:
        conn = self._get_conn()
        conn.executemany(
            """INSERT OR REPLACE INTO dependencies
               (dependency_id, source_file_id, target_file_id, workspace_id,
                import_path, resolved)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (
                    d.dependency_id,
                    d.source_file_id,
                    d.target_file_id,
                    d.workspace_id,
                    d.import_path,
                    1 if d.resolved else 0,
                )
                for d in deps
            ],
        )
        conn.commit()

    def get_file_dependencies(self, file_id: str) -> list[Dependency]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM dependencies WHERE source_file_id = ?", (file_id,)
        ).fetchall()
        return [self._row_to_dependency(r) for r in rows]

    def get_workspace_dependencies(self, workspace_id: str) -> list[Dependency]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM dependencies WHERE workspace_id = ?", (workspace_id,)
        ).fetchall()
        return [self._row_to_dependency(r) for r in rows]

    def delete_file_dependencies(self, file_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM dependencies WHERE source_file_id = ?", (file_id,))
        conn.commit()

    def save_job(self, job: IndexJob) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO index_jobs
               (job_id, workspace_id, status, files_total, files_processed,
                files_failed, symbols_extracted, created_at, started_at,
                completed_at, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job.job_id,
                job.workspace_id,
                job.status.value,
                job.files_total,
                job.files_processed,
                job.files_failed,
                job.symbols_extracted,
                job.created_at,
                job.started_at,
                job.completed_at,
                job.error_message,
            ),
        )
        conn.commit()

    def get_job(self, job_id: str) -> IndexJob | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM index_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return self._row_to_job(row)

    def get_workspace_jobs(self, workspace_id: str) -> list[IndexJob]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM index_jobs WHERE workspace_id = ? ORDER BY created_at DESC",
            (workspace_id,),
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def get_workspace_stats(self, workspace_id: str) -> dict:
        conn = self._get_conn()
        file_count = conn.execute(
            "SELECT COUNT(*) FROM files WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()[0]
        symbol_count = conn.execute(
            "SELECT COUNT(*) FROM symbols WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()[0]
        import_count = conn.execute(
            "SELECT COUNT(*) FROM imports WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()[0]
        lang_rows = conn.execute(
            "SELECT language, COUNT(*) as cnt FROM files WHERE workspace_id = ? GROUP BY language",
            (workspace_id,),
        ).fetchall()
        languages = {r["language"]: r["cnt"] for r in lang_rows}
        return {
            "file_count": file_count,
            "symbol_count": symbol_count,
            "import_count": import_count,
            "languages": languages,
        }

    def _row_to_file(self, row: sqlite3.Row) -> FileRecord:
        return FileRecord(
            file_id=row["file_id"],
            workspace_id=row["workspace_id"],
            relative_path=row["relative_path"],
            language=row["language"],
            size=row["size"],
            mtime=row["mtime"],
            content_hash=row["content_hash"],
            status=FileStatus(row["status"]),
            symbol_count=row["symbol_count"],
            parse_status=row["parse_status"],
            is_binary=bool(row["is_binary"]),
        )

    def _row_to_symbol(self, row: sqlite3.Row) -> Symbol:
        return Symbol(
            symbol_id=row["symbol_id"],
            file_id=row["file_id"],
            workspace_id=row["workspace_id"],
            name=row["name"],
            kind=SymbolKind(row["kind"]),
            language=row["language"],
            start_line=row["start_line"],
            start_column=row["start_column"],
            end_line=row["end_line"],
            end_column=row["end_column"],
            parent_symbol_id=row["parent_symbol_id"],
            visibility=row["visibility"],
            signature=row["signature"],
            documentation=row["documentation"],
            qualified_name=row["qualified_name"],
        )

    def _row_to_import(self, row: sqlite3.Row) -> ImportReference:
        from .models import ImportKind

        return ImportReference(
            import_id=row["import_id"],
            file_id=row["file_id"],
            workspace_id=row["workspace_id"],
            import_path=row["import_path"],
            import_kind=ImportKind(row["import_kind"]),
            imported_names=json.loads(row["imported_names"]),
            line=row["line"],
        )

    def _row_to_dependency(self, row: sqlite3.Row) -> Dependency:
        return Dependency(
            dependency_id=row["dependency_id"],
            source_file_id=row["source_file_id"],
            target_file_id=row["target_file_id"],
            workspace_id=row["workspace_id"],
            import_path=row["import_path"],
            resolved=bool(row["resolved"]),
        )

    def _row_to_job(self, row: sqlite3.Row) -> IndexJob:
        return IndexJob(
            job_id=row["job_id"],
            workspace_id=row["workspace_id"],
            status=JobStatus(row["status"]),
            files_total=row["files_total"],
            files_processed=row["files_processed"],
            files_failed=row["files_failed"],
            symbols_extracted=row["symbols_extracted"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error_message=row["error_message"],
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
