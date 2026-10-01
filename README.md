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

# Open the Web UI (chat + API key settings)
# http://127.0.0.1:8000/ui
```

## Web UI

`codeforge serve` serves a built-in web UI at [http://127.0.0.1:8000/ui](http://127.0.0.1:8000/ui)
(no build step, no Node required):

- **Provider API Keys** — enter/clear OpenAI and Gemini keys; saved to `.env`
  (mode 600, gitignored), applied immediately, never returned in full
- **Model picker** — list local + remote models, load/unload
- **Chat** — plain and remote models through the same interface

## Model Providers (OpenAI / Gemini / Local)

Select a backend by model id prefix — see [docs/providers.md](docs/providers.md):

| Model ID | Backend |
|---|---|
| `tiny-random-gpt2`, ... | Local (PyTorch) |
| `openai:gpt-4o-mini` | OpenAI API |
| `gemini:gemini-2.5-flash` | Gemini API |

```bash
# Keys via .env (or the Web UI), standard names:
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
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
- [x] Phase 9: Secure Tool System
- [x] Phase 10: File Editing + Terminal
- [x] Phase 11: Agent Engine

### Remaining

- [ ] Phase 12: Memory
- [ ] Phase 13: Security Hardening
- [ ] Phase 14: Cross-platform Packaging
- [ ] Phase 15: Performance Optimization

## Project Structure

```
CodeForge-AI/
  codeforge/           # Main Python package
    packages/          # Core packages
      hardware/        # Phase 1: Hardware detection
      runtime/         # Phase 2: Runtime abstraction
      models/          # Phase 3: Model management (incl. remote/ providers)
      generation/      # Phase 4: Text generation
      indexing/        # Phase 7: Repository indexing
      embeddings/      # Phase 8: Embedding providers
      chunks/          # Phase 8: Code chunking
      vector/          # Phase 8: Vector store
      search/           # Phase 8: Search engine
      rag/              # Phase 8: RAG pipeline
      tools/            # Phase 9/10: Tool system (incl. write/edit/run tools)
      file_editing/     # Phase 10: Safe file editing (policy + atomic writes)
      terminal/         # Phase 10: Safe terminal (policy-gated execution)
      agent/            # Phase 11: Agent engine (LLM tool-use loop)
    api/               # FastAPI server (Phase 5) + Web UI (static/)
    cli.py             # CLI entry point
  codeforge-vscode/    # VS Code extension (Phase 6)
  tests/               # Test suite
  docs/                # Documentation
```

## Testing

```bash
# Run all tests
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

# File Editing (Phase 10)
codeforge file read src/app.py -w myws     # Read a workspace file
codeforge file write notes.md -w myws -c "hello"  # Atomic write (stdin ok)
codeforge file edit src/app.py -w myws --old "a" --new "b"  # Exact replace

# Terminal (Phase 10)
codeforge terminal doctor        # Terminal diagnostics
codeforge terminal policy        # Show command policy
codeforge terminal execute ls    # Policy-checked execution

# Agent (Phase 11)
codeforge agent "Add docstrings to utils.py" -m tiny-random-gpt2 -w myws
codeforge agent "Summarize the repo" -m openai:gpt-4o-mini --allow read_file

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
- `POST /v1/chat` — Chat (local or `openai:` / `gemini:` models)

### Settings (Web UI)
- `GET /v1/settings/providers` — Provider status (keys masked)
- `PUT /v1/settings/providers` — Save/clear provider API keys (persisted to `.env`)

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

### File Editing (Phase 10)
- `POST /v1/files/read` — Read a workspace file
- `POST /v1/files/write` — Write a workspace file (atomic, `create_only` option)
- `POST /v1/files/str-replace` — Exact-match replace with diff
- `GET /v1/files/policy` — Effective file-editing policy

### Terminal (Phase 10)
- `POST /v1/terminal/execute` — Policy-gated command execution
- `GET /v1/terminal/policy` — Command classification policy
- `GET /v1/terminal/health` — Terminal health

### Tools (Phase 9/10)
- `GET /v1/tools` — List registered tools
- `POST /v1/tools/{name}/execute` — Execute a tool
- `GET /v1/tools/health` — Tool system health
- `PUT /v1/tools/policy` — Configure tool permission policy

### Agent (Phase 11)
- `POST /v1/agent/run` — Run an agent task to completion
- `GET /v1/agent/tasks` — List agent sessions
- `GET /v1/agent/tasks/{id}` — Get agent task result
- `DELETE /v1/agent/tasks/{id}` — Drop an agent session
- `POST /v1/agent/tasks/{id}/cancel` — Cancel a running agent task
- `GET /v1/agent/health` — Agent engine health

### OpenAI Compatible
- `POST /v1/chat/completions` — Chat completions
- `POST /v1/completions` — Text completions

## License

MIT
