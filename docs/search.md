# Hybrid Search + Embeddings + RAG (Phase 8)

Local-first repository-aware search and retrieval-augmented generation.

## Architecture

```
User Query
    ↓
QueryAnalyzer
    ↓
┌─────────┬──────────┬──────────┐
│ Lexical │ Symbol   │ Semantic │
│ Search  │ Search   │ Search   │
└────┬────┴────┬─────┴────┬─────┘
     └────────┼──────────┘
              ↓
        HybridRanker
              ↓
        ContextBuilder
              ↓
           RAG
              ↓
      GenerationService
              ↓
         Local LLM
```

## Packages

| Package | Purpose |
|---------|---------|
| `embeddings` | Embedding providers, cache, management |
| `chunks` | Structural code chunking |
| `vector` | Vector store abstraction and in-memory implementation |
| `search` | Lexical, symbol, semantic, hybrid search |
| `rag` | RAG service, context building, citations |

## Embeddings

### Providers

```python
from codeforge.packages.embeddings import EmbeddingManager, EmbeddingConfig

manager = EmbeddingManager(config=EmbeddingConfig(dimension=384))
result = manager.embed("def hello(): pass")
print(result.embedding.dimension)  # 384
```

### Cache

Embeddings are cached in SQLite:
- Cache key = content hash + model ID
- Invalidated when content changes
- Supports prefix invalidation

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `provider` | `local` | Embedding provider |
| `model` | `default` | Model identifier |
| `device` | `cpu` | Compute device |
| `batch_size` | `32` | Batch size |
| `normalize` | `true` | Normalize vectors |
| `dimension` | `384` | Vector dimension |

## Code Chunking

Structural chunking based on AST boundaries:

```python
from codeforge.packages.chunks import CodeChunker

chunker = CodeChunker()
chunks = chunker.chunk_file(source, "python", symbols=symbols)
```

### Chunk Boundaries

| Language | Boundaries |
|----------|-----------|
| Python | class, function, method |
| JavaScript | class, function |
| TypeScript | class, interface, function |
| Java | class, method |
| Go | function, struct |
| Rust | fn, struct, impl |

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `max_chunk_tokens` | `512` | Max tokens per chunk |
| `overlap_tokens` | `50` | Overlap between chunks |
| `min_chunk_tokens` | `50` | Minimum chunk size |

## Vector Store

### Interface

```python
from codeforge.packages.vector import VectorStore

class VectorStore(ABC):
    def add(record: VectorRecord) -> str
    def upsert(record: VectorRecord) -> str
    def delete(record_id: str) -> bool
    def search(query_embedding, workspace_id, top_k) -> list[SearchResult]
    def count(workspace_id) -> int
```

### In-Memory Implementation

- Cosine similarity search
- Workspace isolation
- Upsert support
- No external dependencies

## Search

### Lexical Search

```python
from codeforge.packages.search import LexicalSearch, SearchQuery

search = LexicalSearch()
results = search.search(
    SearchQuery(query="UserService"),
    chunks=chunks,
)
```

Features:
- Exact substring matching
- Case-sensitive/insensitive
- Regex support
- Language filtering
- Position-based scoring

### Symbol Search

```python
from codeforge.packages.search import SymbolSearch

search = SymbolSearch()
results = search.search(query, symbols, chunks)
```

Features:
- Exact name matching
- Qualified name matching
- Partial matching
- Kind-based filtering

### Semantic Search

```python
from codeforge.packages.search import SemanticSearch

search = SemanticSearch(vector_store, embedding_manager)
results = search.search(query)
```

Features:
- Vector similarity (cosine)
- Embedding-based
- Workspace-filtered

### Hybrid Search

```python
from codeforge.packages.search import HybridSearch

hybrid = HybridSearch(
    lexical_weight=0.3,
    semantic_weight=0.4,
    symbol_weight=0.3,
)
results = hybrid.search(query, chunks, symbols)
```

Features:
- Score normalization
- Weighted combination
- Result deduplication
- Configurable weights

## RAG

### Flow

1. **Query Analysis** — Determine search intent
2. **Search** — Execute lexical + symbol + semantic
3. **Rank** — Hybrid score combination
4. **Deduplicate** — Merge identical results
5. **Context Build** — Select top chunks within token budget
6. **Prompt** — Construct RAG prompt with citations
7. **Generate** — Send to GenerationService

### RAG Service

```python
from codeforge.packages.rag import RAGService, RAGQuery

service = RAGService(hybrid_search)
service.update_context(chunks, symbols)

response = service.query(RAGQuery(
    workspace_id="ws1",
    query="How does authentication work?",
    top_k=8,
))
print(response.answer)
print(response.sources)
```

### Source Citations

Every RAG response includes source references:

```python
for source in response.sources:
    print(f"{source.file_path}:{source.start_line}-{source.end_line}")
```

### Prompt Injection Defense

- Retrieved code treated as untrusted data
- System instructions separated from context
- Clear delimiters between system/context/user

### Token Budget

```python
builder = ContextBuilder(RAGConfig(max_context_tokens=4000))
context, sources = builder.build_context(search_results)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/search` | Search repository |
| POST | `/v1/rag/query` | RAG query |
| POST | `/v1/workspaces/{id}/embeddings/index` | Build embeddings |
| GET | `/v1/workspaces/{id}/embeddings/status` | Embedding status |
| POST | `/v1/workspaces/{id}/embeddings/rebuild` | Rebuild embeddings |
| POST | `/v1/workspaces/{id}/embeddings/cancel` | Cancel embedding |

### Search Request

```json
{
    "workspace_id": "...",
    "query": "UserService",
    "mode": "hybrid",
    "limit": 10,
    "language": "python"
}
```

### RAG Request

```json
{
    "workspace_id": "...",
    "query": "How does authentication work?",
    "model": "local-model",
    "top_k": 8,
    "stream": false
}
```

## Configuration

```yaml
search:
    default_mode: hybrid
    max_results: 20
    lexical_weight: 0.3
    semantic_weight: 0.4
    symbol_weight: 0.3

embeddings:
    provider: local
    model: default
    device: auto
    batch_size: 32
    normalize: true
    dimension: 384

rag:
    enabled: true
    top_k: 8
    max_context_tokens: 4000
    include_sources: true
```

## Security

- **Workspace isolation** — Queries filter by workspace_id
- **No cross-workspace retrieval**
- **Prompt injection defense** — Untrusted content delimiters
- **Token budget limits** — Prevents context overflow
- **No external cloud requests** — Local-first

## Limitations

- In-memory vector store (no persistence)
- No FAISS/HNSW indexing
- Fallback hash embeddings (not real semantic)
- No cross-file symbol resolution
- Regex-based chunking (not full AST)
- No real LLM generation in RAG

## Tests

48 tests covering:
- Embedding provider, cache, manager
- Code chunking
- Vector store operations
- Lexical search
- Symbol search
- Hybrid search
- Context building
- Token budget
- RAG service
- Source citations

```bash
python -m pytest tests/unit/test_search_rag.py -v
```
