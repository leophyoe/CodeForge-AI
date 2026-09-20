from __future__ import annotations

import threading
import time
from pathlib import Path

from .errors import IndexingError
from .languages import is_source_language
from .models import (
    Dependency,
    FileRecord,
    FileStatus,
    IndexJob,
    IndexStatus,
    JobStatus,
    Workspace,
)
from .parser import CodeParser
from .scanner import FileScanner
from .storage import Storage
from .symbols import SymbolExtractor


class Indexer:
    def __init__(self, storage: Storage | None = None) -> None:
        self.storage = storage or Storage()
        self.scanner = FileScanner()
        self.parser = CodeParser()
        self.extractor = SymbolExtractor()
        self._active_jobs: dict[str, threading.Event] = {}

    def create_workspace(self, root_path: str, name: str = "") -> Workspace:
        root = Path(root_path).resolve()
        if not root.exists():
            raise IndexingError(f"Path does not exist: {root_path}")
        if not root.is_dir():
            raise IndexingError(f"Path is not a directory: {root_path}")

        ws = Workspace(
            root_path=str(root),
            name=name or root.name,
        )
        self.storage.save_workspace(ws)
        return ws

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        return self.storage.get_workspace(workspace_id)

    def list_workspaces(self) -> list[Workspace]:
        return self.storage.list_workspaces()

    def delete_workspace(self, workspace_id: str) -> bool:
        self.storage.delete_workspace_files(workspace_id)
        return self.storage.delete_workspace(workspace_id)

    def index_workspace(
        self, workspace_id: str, background: bool = True
    ) -> IndexJob:
        ws = self.storage.get_workspace(workspace_id)
        if not ws:
            raise IndexingError(f"Workspace not found: {workspace_id}")

        job = IndexJob(workspace_id=workspace_id, status=JobStatus.QUEUED)
        self.storage.save_job(job)

        if background:
            thread = threading.Thread(
                target=self._run_index_job,
                args=(workspace_id, job.job_id),
                daemon=True,
            )
            thread.start()
        else:
            self._run_index_job(workspace_id, job.job_id)
            job = self.storage.get_job(job.job_id) or job

        return job

    def cancel_job(self, job_id: str) -> bool:
        event = self._active_jobs.get(job_id)
        if event:
            event.set()
            return True
        return False

    def get_job(self, job_id: str) -> IndexJob | None:
        return self.storage.get_job(job_id)

    def _run_index_job(self, workspace_id: str, job_id: str) -> None:
        cancel_event = self._active_jobs.get(job_id)
        if cancel_event is None:
            cancel_event = threading.Event()
            self._active_jobs[job_id] = cancel_event

        ws = self.storage.get_workspace(workspace_id)
        if not ws:
            return

        job = self.storage.get_job(job_id)
        if not job:
            return

        job.status = JobStatus.RUNNING
        job.started_at = time.time()
        self.storage.save_job(job)

        self.storage.get_workspace(workspace_id)
        ws.index_status = IndexStatus.INDEXING
        self.storage.save_workspace(ws)

        try:
            scan_result = self.scanner.scan(Path(ws.root_path), workspace_id)
            job.files_total = len(scan_result.files)
            self.storage.save_job(job)

            for i, file_record in enumerate(scan_result.files):
                if cancel_event.is_set():
                    job.status = JobStatus.CANCELLED
                    self.storage.save_job(job)
                    return

                self._index_file(file_record, ws.root_path)
                job.files_processed = i + 1
                job.symbols_extracted = sum(
                    f.symbol_count for f in scan_result.files[: i + 1]
                )
                if (i + 1) % 50 == 0:
                    self.storage.save_job(job)

            job.status = JobStatus.COMPLETED
            job.completed_at = time.time()
            self.storage.save_job(job)

            ws.index_status = IndexStatus.READY
            ws.updated_at = time.time()
            self.storage.save_workspace(ws)

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = time.time()
            self.storage.save_job(job)

            ws.index_status = IndexStatus.ERROR
            self.storage.save_workspace(ws)

        finally:
            self._active_jobs.pop(job_id, None)

    def _index_file(self, file_record: FileRecord, root_path: str) -> None:
        file_path = Path(root_path) / file_record.relative_path

        existing = self.storage.get_file_by_path(
            file_record.workspace_id, file_record.relative_path
        )

        if existing and existing.content_hash == file_record.content_hash:
            file_record.status = FileStatus.INDEXED
            file_record.symbol_count = existing.symbol_count
            self.storage.save_file(file_record)
            return

        file_record.status = FileStatus.INDEXING
        self.storage.save_file(file_record)

        try:
            source = file_path.read_bytes()
        except OSError:
            file_record.status = FileStatus.ERROR
            file_record.parse_status = "READ_ERROR"
            self.storage.save_file(file_record)
            return

        language = file_record.language
        if not is_source_language(language):
            file_record.status = FileStatus.INDEXED
            file_record.symbol_count = 0
            self.storage.save_file(file_record)
            return

        parse_result = self.parser.parse(source, language)
        if parse_result.has_errors:
            file_record.parse_status = f"ERRORS:{parse_result.error_count}"
        else:
            file_record.parse_status = "OK"

        symbols = self.extractor.extract_symbols(
            source, language, file_record.file_id, file_record.workspace_id
        )
        imports = self.extractor.extract_imports(
            source, language, file_record.file_id, file_record.workspace_id
        )
        exports = self.extractor.extract_exports(
            source, language, file_record.file_id, file_record.workspace_id
        )

        if existing:
            self.storage.delete_file_symbols(existing.file_id)
            self.storage.delete_file_imports(existing.file_id)
            self.storage.delete_file_exports(existing.file_id)
            self.storage.delete_file_dependencies(existing.file_id)

        file_record.symbol_count = len(symbols)
        file_record.status = FileStatus.INDEXED
        self.storage.save_file(file_record)

        if symbols:
            self.storage.save_symbols(symbols)
        if imports:
            self.storage.save_imports(imports)
        if exports:
            for exp in exports:
                exp["export_id"] = f"{file_record.file_id}_{exp['export_name']}"
            self.storage.save_exports(exports)

        self._build_dependencies(file_record, imports)

    def _build_dependencies(
        self, file_record: FileRecord, imports: list
    ) -> None:
        deps: list[Dependency] = []

        for imp in imports:
            target_file = self._resolve_import(
                imp.import_path, file_record, file_record.workspace_id
            )
            resolved = target_file is not None
            dep = Dependency(
                source_file_id=file_record.file_id,
                target_file_id=target_file.file_id if target_file else "",
                workspace_id=file_record.workspace_id,
                import_path=imp.import_path,
                resolved=resolved,
            )
            deps.append(dep)

        if deps:
            self.storage.save_dependencies(deps)

    def _resolve_import(
        self, import_path: str, file_record: FileRecord, workspace_id: str
    ) -> FileRecord | None:
        if not import_path.startswith("."):
            return None

        source_dir = Path(file_record.relative_path).parent
        resolved = (source_dir / import_path).resolve()
        rel = str(resolved).lstrip("/")

        for ext in ("", ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs"):
            candidate = rel + ext
            found = self.storage.get_file_by_path(workspace_id, candidate)
            if found:
                return found

        return None

    def refresh_file(self, workspace_id: str, relative_path: str) -> FileRecord | None:
        ws = self.storage.get_workspace(workspace_id)
        if not ws:
            return None

        file_path = Path(ws.root_path) / relative_path
        if not file_path.exists():
            existing = self.storage.get_file_by_path(workspace_id, relative_path)
            if existing:
                self.storage.delete_file(existing.file_id)
            return None

        from .languages import detect_language
        from .models import file_hash

        try:
            stat = file_path.stat()
            content = file_path.read_bytes()
        except OSError:
            return None

        language = detect_language(file_path, content)
        record = FileRecord(
            workspace_id=workspace_id,
            relative_path=relative_path,
            language=language,
            size=stat.st_size,
            mtime=stat.st_mtime,
            content_hash=file_hash(content),
            status=FileStatus.CHANGED,
        )
        self._index_file(record, ws.root_path)
        return record

    def get_project_structure(self, workspace_id: str) -> dict:
        files = self.storage.get_workspace_files(workspace_id)
        ws = self.storage.get_workspace(workspace_id)
        stats = self.storage.get_workspace_stats(workspace_id)

        dirs: set[str] = set()
        file_dicts: list[dict] = []
        for f in files:
            parts = Path(f.relative_path).parts
            for i in range(1, len(parts)):
                dirs.add(str(Path(*parts[:i])))
            file_dicts.append({
                "path": f.relative_path,
                "language": f.language,
                "size": f.size,
                "status": f.status.value,
                "symbol_count": f.symbol_count,
            })

        return {
            "workspace_id": workspace_id,
            "root_path": ws.root_path if ws else "",
            "directories": sorted(dirs),
            "files": file_dicts,
            "statistics": stats,
        }
