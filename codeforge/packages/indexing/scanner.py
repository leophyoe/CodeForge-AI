from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import ScannerError
from .ignore import IgnoreRules, is_binary_file
from .languages import detect_language
from .models import FileRecord, FileStatus


@dataclass
class ScanResult:
    files: list[FileRecord]
    ignored_count: int = 0
    binary_count: int = 0
    too_large_count: int = 0
    error_count: int = 0


class FileScanner:
    def __init__(
        self,
        ignore_rules: IgnoreRules | None = None,
        max_file_size: int = 5 * 1024 * 1024,
        follow_symlinks: bool = False,
    ) -> None:
        self.ignore_rules = ignore_rules or IgnoreRules()
        self.max_file_size = max_file_size
        self.follow_symlinks = follow_symlinks

    def scan(self, root: Path, workspace_id: str = "") -> ScanResult:
        if not root.exists():
            raise ScannerError(f"Path does not exist: {root}")
        if not root.is_dir():
            raise ScannerError(f"Path is not a directory: {root}")

        gitignore_path = root / ".gitignore"
        self.ignore_rules.load_gitignore(gitignore_path)

        result = ScanResult(files=[])
        self._scan_directory(root, root, workspace_id, result)
        return result

    def _scan_directory(
        self,
        current: Path,
        root: Path,
        workspace_id: str,
        result: ScanResult,
    ) -> None:
        try:
            entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return
        except OSError:
            return

        for entry in entries:
            if entry.is_dir():
                rel_dir = str(entry.relative_to(root))
                if entry.name in self.ignore_rules.ignore_dirs:
                    continue
                if self.ignore_rules.should_ignore_dir(entry.name, rel_dir):
                    continue
                if entry.is_symlink() and not self.follow_symlinks:
                    try:
                        resolved = entry.resolve()
                        if not str(resolved).startswith(str(root.resolve())):
                            continue
                    except OSError:
                        continue
                self._scan_directory(entry, root, workspace_id, result)

            elif entry.is_file():
                rel_path = str(entry.relative_to(root))
                if self.ignore_rules.should_ignore_file(entry, rel_path):
                    result.ignored_count += 1
                    continue

                record = self._create_file_record(entry, root, workspace_id)
                if record.status == FileStatus.TOO_LARGE:
                    result.too_large_count += 1
                elif record.status == FileStatus.BINARY:
                    result.binary_count += 1
                elif record.status == FileStatus.ERROR:
                    result.error_count += 1

                result.files.append(record)

    def _create_file_record(
        self,
        file_path: Path,
        root: Path,
        workspace_id: str,
    ) -> FileRecord:
        rel_path = str(file_path.relative_to(root))

        try:
            stat = file_path.stat()
        except OSError:
            return FileRecord(
                workspace_id=workspace_id,
                relative_path=rel_path,
                status=FileStatus.ERROR,
            )

        if stat.st_size > self.max_file_size:
            return FileRecord(
                workspace_id=workspace_id,
                relative_path=rel_path,
                size=stat.st_size,
                mtime=stat.st_mtime,
                status=FileStatus.TOO_LARGE,
            )

        if is_binary_file(file_path):
            language = detect_language(file_path)
            return FileRecord(
                workspace_id=workspace_id,
                relative_path=rel_path,
                language=language,
                size=stat.st_size,
                mtime=stat.st_mtime,
                status=FileStatus.BINARY,
                is_binary=True,
            )

        try:
            content = file_path.read_bytes()
        except OSError:
            return FileRecord(
                workspace_id=workspace_id,
                relative_path=rel_path,
                size=stat.st_size,
                mtime=stat.st_mtime,
                status=FileStatus.ERROR,
            )

        from .models import file_hash

        language = detect_language(file_path, content)
        return FileRecord(
            workspace_id=workspace_id,
            relative_path=rel_path,
            language=language,
            size=stat.st_size,
            mtime=stat.st_mtime,
            content_hash=file_hash(content),
            status=FileStatus.DISCOVERED,
        )
