# Phase 8.1 Audit

## Current Architecture

### Packages
| Package | Files | Status |
|---------|-------|--------|
| `indexing/` | 11 | Working, thread-unsafe, stub parser |
| `search/` | 5 | Working but disconnected from workspace |
| `rag/` | 4 | Working but uses fake context |
| `embeddings/` | 4 | Working, thread-unsafe cache |
| `vector/` | 3 | In-memory only, no persistence |
| `chunks/` | 2 | Working |
| `generation/` | 7 | Working |

### Critical Bugs Found
1. `manager.py:43` — `check_symlink_escape()` result discarded, never enforced
2. `routers/search.py:66` — `r.file_path` should be `r.relative_path`
3. `lexical.py:57` — `re.escape()` defeats regex mode

### Fake/Stub Implementations
1. `CodeParser.parse()` — Returns empty ParseResult
2. `RegexParser.parse()` — Only validates, doesn't extract
3. `FallbackEmbeddingProvider` — SHA-512 hash, not real embeddings
4. `RAGService._generate_answer()` — Placeholder
5. CLI `embeddings_index`/`embeddings_status` — Print-only stubs

### Thread Safety Issues
1. `Storage._conn` — Single SQLite connection without lock
2. `EmbeddingCache._conn` — check_same_thread=False but no lock
3. `Indexer._active_jobs` — Shared dict without lock
4. `WorkspaceManager._manager` — Global singleton without protection
5. `InMemoryVectorStore._records` — Dict without thread protection

### Disconnected Components
- Search always passes empty chunks/symbols
- RAG doesn't query workspace index
- No vector persistence
- No index versioning
- No search caching
