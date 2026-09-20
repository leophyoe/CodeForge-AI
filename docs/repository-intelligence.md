# Repository Intelligence & Code Indexing (Phase 7)

CodeForge's Repository Intelligence subsystem provides structural understanding of software repositories without cloud services.

## Architecture

```
Workspace
   │
   ▼
FileScanner
   │
   ▼
IgnoreRules
   │
   ▼
LanguageDetector
   │
   ▼
RegexParser
   │
   ▼
SymbolExtractor
   │
   ▼
RepositoryIndex
   │
   ├── File Index
   ├── Symbol Index
   ├── Import Index
   ├── Export Index
   ├── Dependency Index
   └── Project Structure
```

## Supported Languages

| Language | Symbols | Imports | Exports |
|----------|---------|---------|---------|
| Python | ✅ | ✅ | — |
| JavaScript | ✅ | ✅ | ✅ |
| TypeScript | ✅ | ✅ | ✅ |
| Java | ✅ | ✅ | — |
| C | ✅ | ✅ | — |
| C++ | ✅ | ✅ | — |
| C# | ✅ | ✅ | — |
| Go | ✅ | ✅ | — |
| Rust | ✅ | ✅ | — |
| Ruby | ✅ | ✅ | — |
| PHP | ✅ | ✅ | — |
| Bash | ✅ | ✅ | — |

## Symbol Kinds

- `module` — Python modules, Ruby modules
- `class` — Classes
- `interface` — TypeScript interfaces, Go interfaces, Rust traits
- `struct` — C/C++ structs, Go structs, Rust structs
- `enum` — Enums
- `function` — Functions, standalone methods
- `method` — Class/struct methods
- `variable` — Variables, constants
- `type` — Type aliases
- `constant` — Constants
- `macro` — C/C++ macros

## Usage

### Programmatic

```python
from codeforge.packages.indexing import WorkspaceManager, Storage

# Create manager
manager = WorkspaceManager(allowed_roots=["/home/user/projects"])

# Create and index workspace
ws = manager.create_workspace("/home/user/my-project", "My Project")
job = manager.index_workspace(ws.workspace_id, background=False)

# Query symbols
symbols = manager.find_symbols(ws.workspace_id, name="User")
files = manager.find_files(ws.workspace_id, language="python")
structure = manager.get_project_structure(ws.workspace_id)
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/workspaces` | List workspaces |
| POST | `/v1/workspaces/index` | Index a workspace |
| GET | `/v1/workspaces/{id}` | Get workspace info |
| GET | `/v1/workspaces/{id}/files` | List files |
| GET | `/v1/workspaces/{id}/structure` | Project structure |
| GET | `/v1/workspaces/{id}/symbols` | List symbols |
| GET | `/v1/workspaces/{id}/symbols/{sid}` | Get symbol |
| GET | `/v1/workspaces/{id}/dependencies` | Dependencies |
| POST | `/v1/workspaces/{id}/refresh` | Re-index |
| DELETE | `/v1/workspaces/{id}` | Delete workspace |
| GET | `/v1/jobs/{id}` | Get job status |
| POST | `/v1/jobs/{id}/cancel` | Cancel job |

### Pagination

```bash
GET /v1/workspaces/{id}/symbols?page=1&page_size=100
GET /v1/workspaces/{id}/files?language=python
```

## Indexing Flow

1. **Scan** — Recursively discover files
2. **Filter** — Apply ignore rules (.gitignore, secrets, binaries)
3. **Detect** — Identify programming language
4. **Parse** — Extract syntax structure
5. **Extract** — Gather symbols, imports, exports
6. **Index** — Store in SQLite database
7. **Link** — Build dependency relationships

## Incremental Indexing

The indexer uses content hashing (SHA-256) for change detection:

- **Unchanged files** — Skipped (hash match)
- **Modified files** — Re-parsed
- **New files** — Parsed and indexed
- **Deleted files** — Removed from index

## Background Jobs

Indexing runs in background threads:

```python
# Start background indexing
job = manager.index_workspace(ws.workspace_id, background=True)

# Check progress
job = manager.get_job(job.job_id)
print(f"Progress: {job.files_processed}/{job.files_total}")

# Cancel if needed
manager.indexer.cancel_job(job.job_id)
```

## Security

### Workspace Authorization

```python
manager = WorkspaceManager(allowed_roots=[
    "/home/user/projects",
    "/home/user/repos",
])
```

Unauthorized paths are rejected with `UnauthorizedWorkspaceError`.

### Path Traversal Prevention

- Resolves all paths before authorization
- Blocks `../` traversal attempts
- Validates symlink targets

### Secret Safety

Ignored by default:
- `.env`, `.env.*`
- `*.pem`, `*.key`, `*.p12`
- `id_rsa`, `id_ed25519`

### Binary Detection

- Detects null bytes in file content
- Skips images, archives, executables
- Marks as `BINARY` in index

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `max_file_size` | 5MB | Maximum file size to index |
| `follow_symlinks` | `false` | Follow symbolic links |
| `ignore_dirs` | standard | Directories to skip |
| `allowed_roots` | `[]` | Authorized workspace roots |

## Database Schema

SQLite tables:
- `workspaces` — Workspace metadata
- `files` — File records with status
- `symbols` — Extracted symbols
- `imports` — Import references
- `exports` — Export references
- `dependencies` — File relationships
- `index_jobs` — Background job tracking

## Limitations

- Regex-based parsing (not full AST)
- No semantic analysis
- No type resolution
- No cross-file symbol resolution
- No vector embeddings
- No RAG
- No code execution

## Tests

80 tests covering:
- Workspace validation
- Path traversal prevention
- Ignore rules (.gitignore, secrets)
- Binary detection
- Language detection (all 13 languages)
- Symbol extraction (all languages)
- Import/export extraction
- Dependency tracking
- Incremental indexing
- SQLite storage
- Background jobs
- API endpoints

```bash
python -m pytest tests/unit/test_indexing.py -v
```
