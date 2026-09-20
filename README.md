# CodeForge AI

Local-first, privacy-first AI coding assistant.

## Quick Start

```bash
# Create environment
conda env create -f environment.yml
conda activate codeforge

# Install in development mode
pip install -e ".[dev]"

# Run hardware detection
codeforge hardware

# Run diagnostics
codeforge doctor

# Start API server
uvicorn codeforge.apps.server.app:app --port 8420
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

- [x] Phase 1: Hardware Detection
- [ ] Phase 2: Python / PyTorch Environment
- [ ] Phase 3: Runtime Abstraction
- [ ] Phase 4: Model Loading
- [ ] Phase 5: Text Generation
- [ ] Phase 6: Streaming
- [ ] Phase 7: FastAPI Server
- [ ] Phase 8: VS Code Connection
- [ ] Phase 9: Chat
- [ ] Phase 10: Inline Completion
- [ ] Phase 11: Repository Indexing
- [ ] Phase 12: Hybrid Search
- [ ] Phase 13: RAG
- [ ] Phase 14: Tool System
- [ ] Phase 15: Safe Terminal
- [ ] Phase 16: File Editing and Diff
- [ ] Phase 17: Testing Loop
- [ ] Phase 18: Git Integration
- [ ] Phase 19: Agent Engine
- [ ] Phase 20: Memory
- [ ] Phase 21: Security Hardening
- [ ] Phase 22: Cross-platform Packaging
- [ ] Phase 23: Performance Optimization

## Project Structure

```
CodeForge-AI/
  codeforge/           # Main Python package
    packages/          # Core packages
      hardware/        # Phase 1: Hardware detection
      core/            # Shared utilities
      runtime/         # Model runtime (Phase 3+)
      models/          # Model management (Phase 4+)
      indexing/        # Codebase indexing (Phase 11+)
      search/          # Search engine (Phase 12+)
      rag/             # RAG pipeline (Phase 13+)
      memory/          # Memory system (Phase 20+)
      tools/           # Tool system (Phase 14+)
      security/        # Security (Phase 21+)
      git/             # Git integration (Phase 18+)
    apps/
      server/          # FastAPI server
  tests/               # Test suite
  docs/                # Documentation
```

## Testing

```bash
pytest tests/ -v
ruff check codeforge/ tests/
mypy codeforge/ --ignore-missing-imports
```

## License

MIT
