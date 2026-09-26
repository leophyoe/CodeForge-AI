# CodeForge API Documentation

REST API server for local LLM inference, repository search, tools, and workspace management.

## Overview

The CodeForge API server exposes endpoints to monitor system hardware, manage local model
loading/unloading, run inference (chat, completions, embeddings), search indexed workspaces,
execute approved tools, and run sandboxed terminal commands. Inference is served locally by
the `GenerationService` — no external services are required.

The request pipeline includes middleware for request IDs, security headers, timing, per-IP
rate limiting, and (optionally) CORS and API-key authentication.

## Getting Started

Start the server:

```bash
codeforge serve
# or
python -m codeforge.cli serve
```

The server defaults to `127.0.0.1:8000`. Access the API at `http://127.0.0.1:8000/v1/`.
Interactive docs are served at `/docs` (disable with `CODEFORGE_API_DOCS_ENABLED=false`).

## Configuration

All settings are configured via environment variables:

| Variable | Default | Description |
|---|---|---|
| `CODEFORGE_SERVER_HOST` | `127.0.0.1` | Bind address |
| `CODEFORGE_SERVER_PORT` | `8000` | Listen port |
| `CODEFORGE_SERVER_WORKERS` | `1` | Uvicorn worker count |
| `CODEFORGE_SERVER_LOG_LEVEL` | `info` | Log level |
| `CODEFORGE_API_DOCS_ENABLED` | `true` | Serve `/docs` and `/openapi.json` |
| `CODEFORGE_API_AUTH_REQUIRED` | `false` | Require `X-API-Key` on all endpoints (except `/v1/health`) |
| `CODEFORGE_API_KEY` | (empty) | API key checked when auth is required |
| `CODEFORGE_RATE_LIMIT_ENABLED` | `true` | Enable per-IP rate limiting |
| `CODEFORGE_RATE_LIMIT_REQUESTS_PER_MINUTE` | `60` | Requests per 60s window |
| `CODEFORGE_CORS_ENABLED` | `false` | Enable CORS middleware |
| `CODEFORGE_CORS_ALLOWED_ORIGINS` | (empty) | JSON array, e.g. `["http://localhost:3000"]` |

Note: `codeforge serve` always starts with rate limiting enabled (60/minute).

## Authentication

When `CODEFORGE_API_AUTH_REQUIRED=true`, every endpoint except `GET /v1/health` requires
the `X-API-Key` header. The key is read from `CODEFORGE_API_KEY`. Auth is **fail-closed**:
if auth is enabled but no key is configured, all requests are rejected with `401`. Key
comparison is timing-safe.

```bash
curl -H "X-API-Key: my-secret" http://127.0.0.1:8000/v1/models
```

## Endpoints Reference

### System & Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/health` | Liveness probe — returns `{"status": "ok"}` (exempt from auth and rate limiting) |
| `GET` | `/v1/ready` | Readiness probe — reports loaded model count |
| `GET` | `/v1/system` | OS, CPU, Python, package versions |
| `GET` | `/v1/hardware` | Full CPU/GPU/memory detail |
| `GET` | `/v1/hardware/summary` | Compact hardware overview |
| `GET` | `/v1/hardware/compatibility` | Local vs. Cloud hardware comparison |
| `GET` | `/v1/runtime` | Runtime status (backends, models, GPU) |
| `GET` | `/v1/runtime/smoke-test` | Verify runtime backends respond |

### Model Management

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/models` | List models (OpenAI-compatible `{"object": "list", "data": [...]}` shape) |
| `GET` | `/v1/models/{model_id}` | Get details for a specific model |
| `POST` | `/v1/models/{model_id}/load` | Download/pull a model into memory |
| `POST` | `/v1/models/{model_id}/unload` | Remove a model from memory |
| `GET` | `/v1/models/{model_id}/status` | Check loading/download status |

### Inference

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/chat` | Chat completion (CodeForge format) |
| `POST` | `/v1/completions` | Text completion (CodeForge format) |
| `POST` | `/v1/embeddings` | Embed a single text |
| `POST` | `/v1/embeddings/batch` | Embed a list of texts |
| `GET` | `/v1/embeddings/health` | Embedding pipeline health |
| `GET` | `/v1/embeddings/config` | Current embedding configuration |

### Search

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/search` | Search an indexed workspace — see `docs/search.md` |
| `GET` | `/v1/search/modes` | List available search modes |

### Tools

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/tools` | List registered tools |
| `GET` | `/v1/tools/{tool_name}` | Tool details and schema |
| `POST` | `/v1/tools/{tool_name}/execute` | Execute a tool — see `docs/tools.md` |
| `GET` | `/v1/tools/health` | Tool subsystem health |

### Terminal (Safe Terminal)

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/terminal/execute` | Execute an approved command — see `docs/terminal.md` |
| `GET` | `/v1/terminal/health` | Terminal subsystem health |
| `GET` | `/v1/terminal/policy` | Active terminal security policy |

### Workspaces (Repository Intelligence)

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/workspaces` | List workspaces |
| `POST` | `/v1/workspaces/index` | Index a workspace |
| `GET` | `/v1/workspaces/{workspace_id}` | Workspace details |
| `POST` | `/v1/workspaces/{workspace_id}/refresh` | Refresh workspace files |
| `GET` | `/v1/workspaces/{workspace_id}/structure` | Project structure |
| `GET` | `/v1/workspaces/{workspace_id}/symbols` | List symbols (paginated) |
| `GET` | `/v1/workspaces/{workspace_id}/symbols/{symbol_id}` | Symbol details |
| `GET` | `/v1/workspaces/{workspace_id}/dependencies` | Project dependencies |
| `GET` | `/v1/workspaces/{workspace_id}/files` | Indexed files |
| `GET` | `/v1/workspaces/jobs/{job_id}` | Index job status |
| `POST` | `/v1/workspaces/jobs/{job_id}/cancel` | Cancel an index job |

### OpenAI-Compatible Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat |
| `POST` | `/v1/completions` | OpenAI-compatible completions |
| `GET` | `/v1/models` | OpenAI-compatible model list (same endpoint as above) |

## Streaming Protocol

Streaming responses use Server-Sent Events (SSE). Set `"stream": true` in the request body.

**Format:**
```
data: {"choices":[{"delta":{"content":"Hello"},"index":0}]}

data: {"choices":[{"delta":{},"finish_reason":"stop","index":0}]}

data: [DONE]
```

Each event is prefixed with `data: `. A blank line separates events. The final event is `data: [DONE]`.

## Error Response Format

Two error shapes are returned, depending on where the error is raised:

`APIError` responses (validation, auth, rate limit, domain errors):

```json
{
  "error": {
    "code": "path_traversal",
    "message": "Invalid path component: '../../etc' contains path traversal sequences.",
    "request_id": "3f1c0e2a-..."
  }
}
```

Route-level validation errors (FastAPI `HTTPException`):

```json
{"detail": "Model 'llama3.2' not found"}
```

Every response (including errors) carries an `X-Request-ID` header. Rate-limited responses
(`429`) include a `Retry-After` header.

Standard HTTP status codes: `400`, `401`, `404`, `409`, `429`, `500`, `503`.

## Security Features

The request pipeline provides:

- **Request IDs** — `X-Request-ID` echoed in response headers and error bodies
- **Security headers** — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`
- **Rate limiting** — per-IP sliding window (default 60/minute) returning `429` with
  `Retry-After`; health checks exempt; client table is memory-bounded
- **API-key authentication** — opt-in, fail-closed, timing-safe (`X-API-Key`)
- **Path traversal protection** — model IDs, workspace paths, and terminal working
  directories reject `../`, absolute paths, and symlink escapes
- **CORS** — configurable allowed origins (disabled by default)

## Client Examples

### Python (requests)

```python
import requests

BASE = "http://127.0.0.1:8000/v1"

# Health check
r = requests.get(f"{BASE}/health")
print(r.json())  # {"status": "ok"}

# List models
r = requests.get(f"{BASE}/models")
models = r.json()["data"]

# Chat completion
r = requests.post(
    f"{BASE}/chat",
    json={"model": "llama3.2", "messages": [{"role": "user", "content": "Hello"}], "stream": False},
)
print(r.json()["choices"][0]["message"]["content"])

# Streaming
r = requests.post(
    f"{BASE}/chat",
    json={
        "model": "llama3.2",
        "messages": [{"role": "user", "content": "Write a haiku"}],
        "stream": True,
    },
    stream=True,
)

for line in r.iter_lines():
    if line and line.startswith(b"data: "):
        print(line.decode().removeprefix("data: "))
```

### curl

```bash
# Health
curl http://127.0.0.1:8000/v1/health

# Models
curl http://127.0.0.1:8000/v1/models

# Chat
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2","messages":[{"role":"user","content":"Hello"}]}'

# Load a model
curl -X POST http://127.0.0.1:8000/v1/models/llama3.2/load

# Unload a model
curl -X POST http://127.0.0.1:8000/v1/models/llama3.2/unload

# With auth enabled
curl -H "X-API-Key: my-secret" http://127.0.0.1:8000/v1/models
```

## LAN Usage Guide

To expose the API on your local network:

```bash
# Bind to all interfaces
CODEFORGE_SERVER_HOST=0.0.0.0 codeforge serve

# Or set port
CODEFORGE_SERVER_HOST=0.0.0.0 CODEFORGE_SERVER_PORT=8000 codeforge serve
```

Access from another device: `http://<your-ip>:8000/v1/health`

**Security note:** When binding to `0.0.0.0`, for LAN access consider:

- Enabling auth: `CODEFORGE_API_AUTH_REQUIRED=true CODEFORGE_API_KEY=<random>`
- Setting `CODEFORGE_CORS_ALLOWED_ORIGINS` to a JSON array of your allowed origins
- Using a firewall to restrict access to the port
- Keeping rate limiting enabled (default)

## OpenAI Compatibility Status

| Feature | Status |
|---|---|
| `/v1/chat/completions` | Supported (local GenerationService) |
| `/v1/completions` | Supported (local GenerationService) |
| `/v1/models` | Supported |
| `/v1/embeddings` | Supported |
| Streaming (SSE) | Supported |
| Function calling | Not implemented |

Model availability depends on what is installed locally (see `codeforge models` and
`docs/models.md`).
