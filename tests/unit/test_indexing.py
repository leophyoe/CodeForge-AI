import shutil
from pathlib import Path

import pytest

from codeforge.packages.indexing.errors import (
    ScannerError,
    UnauthorizedWorkspaceError,
)
from codeforge.packages.indexing.ignore import (
    IgnoreRules,
    is_binary_file,
)
from codeforge.packages.indexing.indexer import Indexer
from codeforge.packages.indexing.languages import (
    detect_language,
    is_source_language,
    is_supported_language,
)
from codeforge.packages.indexing.manager import WorkspaceManager
from codeforge.packages.indexing.models import (
    FileRecord,
    FileStatus,
    ImportReference,
    IndexJob,
    JobStatus,
    Symbol,
    SymbolKind,
    Workspace,
)
from codeforge.packages.indexing.parser import ParseResult, RegexParser
from codeforge.packages.indexing.scanner import FileScanner
from codeforge.packages.indexing.storage import Storage
from codeforge.packages.indexing.symbols import SymbolExtractor

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sample_repository"


@pytest.fixture
def tmp_workspace(tmp_path):
    shutil.copytree(str(FIXTURE_DIR), str(tmp_path / "repo"))
    return tmp_path / "repo"


@pytest.fixture
def storage(tmp_path):
    db = tmp_path / "test.db"
    return Storage(str(db))


@pytest.fixture
def indexer(storage):
    return Indexer(storage)


@pytest.fixture
def manager(storage):
    return WorkspaceManager(storage)


class TestIgnoreRules:
    def test_default_ignore_dirs(self):
        rules = IgnoreRules()
        assert ".git" in rules.ignore_dirs
        assert "node_modules" in rules.ignore_dirs
        assert "__pycache__" in rules.ignore_dirs

    def test_should_ignore_dir(self):
        rules = IgnoreRules()
        assert rules.should_ignore_dir("node_modules") is True
        assert rules.should_ignore_dir("__pycache__") is True
        assert rules.should_ignore_dir("src") is False

    def test_should_ignore_file(self):
        rules = IgnoreRules()
        assert rules.should_ignore_file(Path(".env")) is True
        assert rules.should_ignore_file(Path("test.py")) is False
        assert rules.should_ignore_file(Path("app.pyc")) is True

    def test_secret_detection(self):
        rules = IgnoreRules()
        assert rules.is_secret(Path("id_rsa")) is True
        assert rules.is_secret(Path("server.pem")) is True
        assert rules.is_secret(Path("app.py")) is False

    def test_gitignore_loading(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\ntemp/\n")
        rules = IgnoreRules()
        rules.load_gitignore(gitignore)
        assert rules.should_ignore_file(Path("debug.log")) is True


class TestBinaryDetection:
    def test_text_file_not_binary(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("print('hello')")
        assert is_binary_file(f) is False

    def test_binary_file_detected(self, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00\x01\x02\x03\x00\x01\x02\x03")
        assert is_binary_file(f) is True

    def test_empty_file_not_binary(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        assert is_binary_file(f) is False


class TestLanguageDetection:
    def test_python_detection(self):
        assert detect_language(Path("app.py")) == "python"

    def test_javascript_detection(self):
        assert detect_language(Path("app.js")) == "javascript"
        assert detect_language(Path("app.jsx")) == "javascript"

    def test_typescript_detection(self):
        assert detect_language(Path("app.ts")) == "typescript"
        assert detect_language(Path("app.tsx")) == "typescript"

    def test_java_detection(self):
        assert detect_language(Path("App.java")) == "java"

    def test_go_detection(self):
        assert detect_language(Path("main.go")) == "go"

    def test_rust_detection(self):
        assert detect_language(Path("main.rs")) == "rust"

    def test_c_detection(self):
        assert detect_language(Path("main.c")) == "c"
        assert detect_language(Path("main.h")) == "c"

    def test_cpp_detection(self):
        assert detect_language(Path("main.cpp")) == "cpp"

    def test_csharp_detection(self):
        assert detect_language(Path("Program.cs")) == "csharp"

    def test_html_detection(self):
        assert detect_language(Path("index.html")) == "html"

    def test_css_detection(self):
        assert detect_language(Path("style.css")) == "css"

    def test_bash_detection(self):
        assert detect_language(Path("script.sh")) == "bash"

    def test_dockerfile_detection(self):
        assert detect_language(Path("Dockerfile")) == "dockerfile"

    def test_unknown_extension(self):
        assert detect_language(Path("unknown.xyz")) == "unknown"

    def test_shebang_detection(self, tmp_path):
        f = tmp_path / "script"
        content = b"#!/usr/bin/env python3\nprint('hello')"
        f.write_bytes(content)
        assert detect_language(f, content) == "python"

    def test_is_source_language(self):
        assert is_source_language("python") is True
        assert is_source_language("javascript") is True
        assert is_source_language("html") is False

    def test_is_supported_language(self):
        assert is_supported_language("python") is True
        assert is_supported_language("cobol") is False


class TestFileScanner:
    def test_scan_fixture(self, tmp_workspace):
        scanner = FileScanner()
        result = scanner.scan(tmp_workspace)
        assert len(result.files) > 0
        paths = [f.relative_path for f in result.files]
        assert any("main.py" in p for p in paths)

    def test_scan_ignores_git(self, tmp_workspace):
        git_dir = tmp_workspace / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("test")
        scanner = FileScanner()
        result = scanner.scan(tmp_workspace)
        git_files = [f for f in result.files if f.relative_path.startswith(".git/")]
        assert len(git_files) == 0

    def test_scan_ignores_env(self, tmp_workspace):
        (tmp_workspace / ".env").write_text("SECRET=123")
        scanner = FileScanner()
        result = scanner.scan(tmp_workspace)
        assert not any(f.relative_path == ".env" for f in result.files)

    def test_scan_respects_max_file_size(self, tmp_workspace):
        (tmp_workspace / "big.py").write_bytes(b"x" * (6 * 1024 * 1024))
        scanner = FileScanner(max_file_size=5 * 1024 * 1024)
        result = scanner.scan(tmp_workspace)
        assert any(f.status == FileStatus.TOO_LARGE for f in result.files)

    def test_scan_nonexistent_path(self):
        scanner = FileScanner()
        with pytest.raises(ScannerError):
            scanner.scan(Path("/nonexistent/path"))

    def test_scan_file_not_dir(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        scanner = FileScanner()
        with pytest.raises(ScannerError):
            scanner.scan(f)


class TestSymbolExtractor:
    def test_python_class_extraction(self):
        source = b"class User:\n    def save(self):\n        pass\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "python")
        names = [s.name for s in symbols]
        assert "User" in names
        assert "save" in names

    def test_python_function_extraction(self):
        source = b"def calculate(x, y):\n    return x + y\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "python")
        assert len(symbols) == 1
        assert symbols[0].name == "calculate"
        assert symbols[0].kind == SymbolKind.FUNCTION

    def test_python_import_extraction(self):
        source = b"import os\nfrom pathlib import Path\n"
        extractor = SymbolExtractor()
        imports = extractor.extract_imports(source, "python")
        assert len(imports) == 2

    def test_javascript_function_extraction(self):
        source = b"function calculate(a, b) { return a + b; }\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "javascript")
        assert len(symbols) == 1
        assert symbols[0].name == "calculate"

    def test_javascript_class_extraction(self):
        source = b"class User {\n  render() {}\n}\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "javascript")
        names = [s.name for s in symbols]
        assert "User" in names

    def test_typescript_interface_extraction(self):
        source = b"interface UserProps {\n  name: string;\n}\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "typescript")
        names = [s.name for s in symbols]
        assert "UserProps" in names

    def test_typescript_enum_extraction(self):
        source = b"enum Status {\n  Active,\n  Inactive\n}\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "typescript")
        names = [s.name for s in symbols]
        assert "Status" in names

    def test_go_function_extraction(self):
        source = b"func Calculate(x int) int {\n  return x * 2\n}\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "go")
        assert len(symbols) == 1
        assert symbols[0].name == "Calculate"

    def test_go_struct_extraction(self):
        source = b"type User struct {\n  Name string\n}\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "go")
        names = [s.name for s in symbols]
        assert "User" in names

    def test_rust_function_extraction(self):
        source = b"fn calculate(x: i32) -> i32 {\n  x * 2\n}\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "rust")
        assert len(symbols) == 1
        assert symbols[0].name == "calculate"

    def test_rust_struct_extraction(self):
        source = b"pub struct User {\n  name: String,\n}\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "rust")
        names = [s.name for s in symbols]
        assert "User" in names

    def test_java_class_extraction(self):
        source = b"public class User {\n  public void save() {}\n}\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "java")
        names = [s.name for s in symbols]
        assert "User" in names
        assert "save" in names

    def test_csharp_class_extraction(self):
        source = b"public class User {\n  public void Save() {}\n}\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "csharp")
        names = [s.name for s in symbols]
        assert "User" in names

    def test_ruby_class_extraction(self):
        source = b"class User\n  def save\n  end\nend\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "ruby")
        names = [s.name for s in symbols]
        assert "User" in names
        assert "save" in names

    def test_bash_function_extraction(self):
        source = b"hello() {\n  echo hello\n}\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "bash")
        assert len(symbols) == 1
        assert symbols[0].name == "hello"

    def test_import_extraction_javascript(self):
        source = b'import React from "react";\nimport { User } from "./user";\n'
        extractor = SymbolExtractor()
        imports = extractor.extract_imports(source, "javascript")
        assert len(imports) == 2

    def test_import_extraction_typescript(self):
        source = b'import { User } from "./models";\n'
        extractor = SymbolExtractor()
        imports = extractor.extract_imports(source, "typescript")
        assert len(imports) == 1
        assert imports[0].import_path == "./models"

    def test_import_extraction_go(self):
        source = b'import "fmt"\nimport "os"\n'
        extractor = SymbolExtractor()
        imports = extractor.extract_imports(source, "go")
        assert len(imports) >= 1

    def test_import_extraction_rust(self):
        source = b"use std::collections::HashMap;\n"
        extractor = SymbolExtractor()
        imports = extractor.extract_imports(source, "rust")
        assert len(imports) == 1

    def test_import_extraction_java(self):
        source = b"import java.util.List;\nimport java.util.Map;\n"
        extractor = SymbolExtractor()
        imports = extractor.extract_imports(source, "java")
        assert len(imports) == 2

    def test_export_extraction_javascript(self):
        source = b"export function foo() {}\nexport class Bar {}\n"
        extractor = SymbolExtractor()
        exports = extractor.extract_exports(source, "javascript")
        assert len(exports) == 2

    def test_export_extraction_typescript(self):
        source = b"export interface User {}\nexport type Status = string;\n"
        extractor = SymbolExtractor()
        exports = extractor.extract_exports(source, "typescript")
        assert len(exports) == 2

    def test_symbol_positions(self):
        source = b"def hello():\n    pass\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "python")
        assert symbols[0].start_line == 0

    def test_symbol_hierarchy(self):
        source = b"class User:\n    def save(self):\n        pass\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "python")
        class_sym = next(s for s in symbols if s.kind == SymbolKind.CLASS)
        method_sym = next(s for s in symbols if s.kind == SymbolKind.METHOD)
        assert method_sym.parent_symbol_id == class_sym.symbol_id

    def test_qualified_names(self):
        source = b"class User:\n    def save(self):\n        pass\n"
        extractor = SymbolExtractor()
        symbols = extractor.extract_symbols(source, "python")
        method_sym = next(s for s in symbols if s.kind == SymbolKind.METHOD)
        assert method_sym.qualified_name == "User.save"


class TestRegexParser:
    def test_parse_returns_result(self):
        parser = RegexParser()
        result = parser.parse(b"def hello(): pass", "python")
        assert isinstance(result, ParseResult)
        assert result.language == "python"

    def test_parse_python(self):
        parser = RegexParser()
        result = parser.parse(b"class User:\n    pass\n", "python")
        assert result.has_errors is False

    def test_parse_file(self, tmp_workspace):
        parser = RegexParser()
        result = parser.parse_file(tmp_workspace / "src" / "main.py")
        assert result.language == "python"


class TestStorage:
    def test_workspace_crud(self, storage):
        ws = Workspace(root_path="/tmp/test", name="test")
        storage.save_workspace(ws)
        retrieved = storage.get_workspace(ws.workspace_id)
        assert retrieved is not None
        assert retrieved.name == "test"

        all_ws = storage.list_workspaces()
        assert len(all_ws) >= 1

        deleted = storage.delete_workspace(ws.workspace_id)
        assert deleted is True

    def test_file_crud(self, storage):
        ws = Workspace(root_path="/tmp/test", name="test")
        storage.save_workspace(ws)
        f = FileRecord(workspace_id=ws.workspace_id, relative_path="app.py")
        storage.save_file(f)
        retrieved = storage.get_file(f.file_id)
        assert retrieved is not None
        assert retrieved.relative_path == "app.py"

    def test_symbol_crud(self, storage):
        ws = Workspace(root_path="/tmp/test", name="test")
        storage.save_workspace(ws)
        f = FileRecord(workspace_id=ws.workspace_id, relative_path="app.py")
        storage.save_file(f)
        s = Symbol(
            file_id=f.file_id,
            workspace_id=ws.workspace_id,
            name="User",
            kind=SymbolKind.CLASS,
        )
        storage.save_symbols([s])
        found = storage.find_symbols(ws.workspace_id, name="User")
        assert len(found) == 1

    def test_import_crud(self, storage):
        ws = Workspace(root_path="/tmp/test", name="test")
        storage.save_workspace(ws)
        f = FileRecord(workspace_id=ws.workspace_id, relative_path="app.py")
        storage.save_file(f)
        imp = ImportReference(
            file_id=f.file_id,
            workspace_id=ws.workspace_id,
            import_path="os",
        )
        storage.save_imports([imp])
        imports = storage.get_file_imports(f.file_id)
        assert len(imports) == 1

    def test_job_crud(self, storage):
        ws = Workspace(root_path="/tmp/test", name="test")
        storage.save_workspace(ws)
        job = IndexJob(workspace_id=ws.workspace_id)
        storage.save_job(job)
        retrieved = storage.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.status == JobStatus.QUEUED

    def test_workspace_stats(self, storage):
        ws = Workspace(root_path="/tmp/test", name="test")
        storage.save_workspace(ws)
        f = FileRecord(workspace_id=ws.workspace_id, relative_path="app.py", language="python")
        storage.save_file(f)
        stats = storage.get_workspace_stats(ws.workspace_id)
        assert stats["file_count"] >= 1


class TestIndexer:
    def test_create_workspace(self, indexer, tmp_workspace):
        ws = indexer.create_workspace(str(tmp_workspace), "test")
        assert ws.name == "test"
        assert ws.root_path == str(tmp_workspace)

    def test_get_workspace(self, indexer, tmp_workspace):
        ws = indexer.create_workspace(str(tmp_workspace), "test")
        retrieved = indexer.get_workspace(ws.workspace_id)
        assert retrieved is not None

    def test_list_workspaces(self, indexer, tmp_workspace):
        indexer.create_workspace(str(tmp_workspace), "test")
        all_ws = indexer.list_workspaces()
        assert len(all_ws) >= 1

    def test_delete_workspace(self, indexer, tmp_workspace):
        ws = indexer.create_workspace(str(tmp_workspace), "test")
        deleted = indexer.delete_workspace(ws.workspace_id)
        assert deleted is True

    def test_index_workspace(self, indexer, tmp_workspace):
        ws = indexer.create_workspace(str(tmp_workspace), "test")
        job = indexer.index_workspace(ws.workspace_id, background=False)
        assert job.status == JobStatus.COMPLETED
        assert job.files_processed > 0

    def test_get_project_structure(self, indexer, tmp_workspace):
        ws = indexer.create_workspace(str(tmp_workspace), "test")
        indexer.index_workspace(ws.workspace_id, background=False)
        structure = indexer.get_project_structure(ws.workspace_id)
        assert "files" in structure
        assert len(structure["files"]) > 0

    def test_refresh_file(self, indexer, tmp_workspace):
        ws = indexer.create_workspace(str(tmp_workspace), "test")
        indexer.index_workspace(ws.workspace_id, background=False)
        result = indexer.refresh_file(ws.workspace_id, "src/main.py")
        assert result is not None


class TestWorkspaceManager:
    def test_create_workspace(self, manager, tmp_workspace):
        ws = manager.create_workspace(str(tmp_workspace), "test")
        assert ws.name == "test"

    def test_allowed_roots(self, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        manager = WorkspaceManager(allowed_roots=[str(allowed)])
        ws = manager.create_workspace(str(allowed), "test")
        assert ws is not None

    def test_unauthorized_workspace(self, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        manager = WorkspaceManager(allowed_roots=[str(allowed)])
        with pytest.raises(UnauthorizedWorkspaceError):
            manager.create_workspace(str(other), "test")

    def test_find_symbols(self, manager, tmp_workspace):
        ws = manager.create_workspace(str(tmp_workspace), "test")
        manager.index_workspace(ws.workspace_id, background=False)
        symbols = manager.find_symbols(ws.workspace_id, name="User")
        assert len(symbols) >= 1

    def test_find_files(self, manager, tmp_workspace):
        ws = manager.create_workspace(str(tmp_workspace), "test")
        manager.index_workspace(ws.workspace_id, background=False)
        files = manager.find_files(ws.workspace_id, language="python")
        assert len(files) >= 1

    def test_get_dependencies(self, manager, tmp_workspace):
        ws = manager.create_workspace(str(tmp_workspace), "test")
        manager.index_workspace(ws.workspace_id, background=False)
        deps = manager.get_dependencies(ws.workspace_id)
        assert isinstance(deps, list)


class TestSecurity:
    def test_path_traversal_prevention(self, storage):
        manager = WorkspaceManager(storage, allowed_roots=["/tmp/allowed"])
        with pytest.raises(UnauthorizedWorkspaceError):
            manager.validate_workspace_path("/etc/passwd")

    def test_symlink_check(self, manager, tmp_workspace):
        manager.create_workspace(str(tmp_workspace), "test")
        assert manager.check_symlink_escape(tmp_workspace, tmp_workspace) is True
