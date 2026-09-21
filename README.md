# CodeForge AI

Local-first, privacy-first AI coding assistant.

## Quick Start

```bash
# Create environment
conda env create -f environment.yml
conda activate codeforge-ai

# Install in development mode
pip install -e ".[dev]"

# Run hardware detection
codeforge hardware

# Run diagnostics
codeforge doctor

# Start API server
codeforge serve
```

## Architecture

```
VS Code Extension
        |
        v
CodeForge AI Client
        |
        v
CodeForge AI Server (FastAPI)
        |
   +----+----+
   |         |
   v         v
Agent     Model
Engine    Runtime
```

## Development Phases

### Completed

- [x] Phase 1: Hardware Detection
- [x] Phase 2: Runtime Abstraction
- [x] Phase 3: Model Management
- [x] Phase 4: Text Generation
- [x] Phase 5: FastAPI Server
- [x] Phase 6: VS Code Extension
- [x] Phase 7: Repository Intelligence
- [x] Phase 8: Hybrid Search + Embeddings + RAG

### Remaining

- [ ] Phase 9: Tool System
- [ ] Phase 10: Safe Terminal
- [ ] Phase 11: File Editing and Diff
- [ ] Phase 12: Testing Loop
- [ ] Phase 13: Git Integration
- [ ] Phase 14: Agent Engine
- [ ] Phase 15: Memory
- [ ] Phase 16: Security Hardening
- [ ] Phase 17: Cross-platform Packaging
- [ ] Phase 18: Performance Optimization

## Project Structure

```
CodeForge-AI/
  codeforge/           # Main Python package
    packages/          # Core packages
      hardware/        # Phase 1: Hardware detection
      runtime/         # Phase 2: Runtime abstraction
      models/          # Phase 3: Model management
      generation/      # Phase 4: Text generation
      indexing/        # Phase 7: Repository indexing
      embeddings/      # Phase 8: Embedding providers
      chunks/          # Phase 8: Code chunking
      vector/          # Phase 8: Vector store
      search/          # Phase 8: Search engine
      rag/             # Phase 8: RAG pipeline
    api/               # FastAPI server (Phase 5)
    cli.py             # CLI entry point
  codeforge-vscode/    # VS Code extension (Phase 6)
  tests/               # Test suite
  docs/                # Documentation
```

## Testing

```bash
# Run all tests (515+ tests)
pytest tests/ -v

# Run specific phase tests
pytest tests/unit/test_search_rag.py -v    # Phase 8: Search + RAG
pytest tests/unit/test_indexing.py -v       # Phase 7: Repository Intelligence
pytest tests/unit/test_api.py -v           # Phase 5: API Server

# Linting
ruff check codeforge/ tests/
```

## CLI Commands

```bash
# Hardware & Diagnostics
codeforge hardware          # Show detected hardware
codeforge doctor            # Run diagnostics

# Runtime
codeforge runtime           # Show runtime info
codeforge device            # List available devices

# Model Management
codeforge models            # List registered models
codeforge model list        # List models
codeforge model inspect     # Inspect model details
codeforge model load        # Load a model
codeforge model unload      # Unload a model
codeforge model discover    # Discover new models

# Generation
codeforge generate          # Generate text
codeforge chat              # Interactive chat

# Search & RAG (Phase 8)
codeforge search "UserService"    # Search code
codeforge rag "How does auth work?"  # RAG query
codeforge embeddings-index        # Build embeddings
codeforge embeddings-status       # Check embedding status

# Server
codeforge serve              # Start API server
```

## API Endpoints

### Health
- `GET /v1/health` — Health check
- `GET /v1/health/ready` — Readiness check

### Hardware
- `GET /v1/hardware` — Hardware info
- `GET /v1/hardware/gpu` — GPU info

### Runtime
- `GET /v1/runtime` — Runtime info
- `GET /v1/runtime/capabilities` — Available capabilities

### Models
- `GET /v1/models` — List models
- `GET /v1/models/{id}` — Get model
- `POST /v1/models/{id}/load` — Load model
- `POST /v1/models/{id}/unload` — Unload model

### Generation
- `POST /v1/generate` — Generate text
- `POST /v1/generate/stream` — Streaming generation

### Embeddings
- `POST /v1/embeddings` — Create embedding
- `POST /v1/embeddings/batch` — Batch embeddings
- `GET /v1/embeddings/health` — Embedding health
- `GET /v1/embeddings/config` — Embedding config

### Search
- `POST /v1/search` — Search code
- `GET /v1/search/modes` — Available search modes

### RAG
- `POST /v1/rag/query` — RAG query

### Workspaces
- `GET /v1/workspaces` — List workspaces
- `POST /v1/workspaces/index` — Index workspace
- `GET /v1/workspaces/{id}` — Get workspace
- `GET /v1/workspaces/{id}/files` — Get files
- `GET /v1/workspaces/{id}/symbols` — Get symbols
- `GET /v1/workspaces/{id}/dependencies` — Get dependencies
- `POST /v1/workspaces/{id}/refresh` — Refresh index

### OpenAI Compatible
- `POST /v1/chat/completions` — Chat completions
- `POST /v1/completions` — Text completions

## License

MIT
