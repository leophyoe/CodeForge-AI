# CodeForge API Documentation

Phase 5 REST API server for local LLM inference management.

## Overview

The CodeForge API server exposes endpoints to monitor system hardware, manage local model loading/unloading, and run inference (chat, completions) against models served by Ollama. It includes a local security proxy that enforces path traversal protection, rate limiting, CORS, and security headers.

## Getting Started

Start the server:

```bash
codeforge serve
# or
python -m codeforge.cli.main serve
```

The server defaults to `127.0.0.1:8327`. Access the API at `http://127.0.0.1:8327/v1/`.

## Configuration

All settings are configured via environment variables:

| Variable | Default | Description |
|---|---|---|
| `CODEFORGE_SERVER_HOST` | `127.0.0.1` | Bind address |
| `CODEFORGE_SERVER_PORT` | `8327` | Listen port |
| `CODEFORGE_SERVER_WORKERS` | `1` | Uvicorn worker count |
| `CODEFORGE_SERVER_LOG_LEVEL` | `info` | Log level |
| `CODEFORGE_SERVER_ALLOW_ALL_ORIGINS` | `false` | Allow any CORS origin |
| `CODEFORGE_SERVER_ALLOWED_ORIGINS` | (empty) | Comma-separated allowed origins |
| `CODEFORGE_SERVER_ENABLE_SECURITY` | `true` | Enable security proxy |
| `CODEFORGE_SERVER_RATE_LIMIT` | `60/minute` | Requests per window |
| `CODEFORGE_SERVER_CORS_ORIGINS` | `http://localhost:3000` | CORS allow list |

## Endpoints Reference

### System & Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/health` | Liveness probe — returns `{"status": "ok"}` |
| `GET` | `/v1/ready` | Readiness probe — checks Ollama connectivity |
| `GET` | `/v1/system` | OS, CPU, Python, package versions |
| `GET` | `/v1/hardware` | Full CPU/GPU/memory detail |
| `GET` | `/v1/hardware/summary` | Compact hardware overview |
| `GET` | `/v1/hardware/compatibility` | Local vs. Cloud hardware comparison |
| `GET` | `/v1/runtime` | Runtime status (Ollama, models, GPU) |
| `GET` | `/v1/runtime/smoke-test` | Verify Ollama is responding |

### Model Management

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/models` | List all available models |
| `GET` | `/v1/models/{model_id}` | Get details for a specific model |
| `POST` | `/v1/models/{model_id}/load` | Download/pull a model into memory |
| `POST` | `/v1/models/{model_id}/unload` | Remove a model from memory |
| `GET` | `/v1/models/{model_id}/status` | Check loading/download status |

### Inference

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/chat` | Chat completion (CodeForge format) |
| `POST` | `/v1/completions` | Text completion (CodeForge format) |
| `POST` | `/v1/embeddings` | Embeddings — **not implemented** (returns 501) |

### OpenAI-Compatible Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat |
| `POST` | `/v1/completions` | OpenAI-compatible completions |
| `GET` | `/v1/models` | OpenAI-compatible model list |

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

All errors follow a consistent structure:

```json
{
  "error": {
    "message": "Model not found: llama3.2",
    "type": "invalid_request_error",
    "code": "model_not_found"
  }
}
```

Standard HTTP status codes: `400`, `404`, `429`, `500`, `503`.

## Security Features

The security proxy (`SecurityProxy` middleware) provides:

- **Path traversal protection** — blocks `../`, encoded variants, and `/etc/passwd`-style paths
- **Rate limiting** — configurable per-IP request throttling (default 60/minute)
- **CORS** — configurable allowed origins, methods, and headers
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Strict-Transport-Security`, `Content-Security-Policy`

Disable with `CODEFORGE_SERVER_ENABLE_SECURITY=false` for local-only trusted use.

## Client Examples

### Python (requests)

```python
import requests

BASE = "http://127.0.0.1:8327/v1"

# Health check
r = requests.get(f"{BASE}/health")
print(r.json())  # {"status": "ok"}

# List models
r = requests.get(f"{BASE}/models")
models = r.json()["data"]

# Chat completion
r = requests.post(f"{BASE}/chat", json={
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": False
})
print(r.json()["choices"][0]["message"]["content"])

# Streaming
r = requests.post(f"{BASE}/chat", json={
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "Write a haiku"}],
    "stream": True
}, stream=True)

for line in r.iter_lines():
    if line and line.startswith(b"data: "):
        print(line.decode().removeprefix("data: "))
```

### curl

```bash
# Health
curl http://127.0.0.1:8327/v1/health

# Models
curl http://127.0.0.1:8327/v1/models

# Chat
curl -X POST http://127.0.0.1:8327/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2","messages":[{"role":"user","content":"Hello"}]}'

# Load a model
curl -X POST http://127.0.0.1:8327/v1/models/llama3.2/load

# Unload a model
curl -X POST http://127.0.0.1:8327/v1/models/llama3.2/unload
```

## LAN Usage Guide

To expose the API on your local network:

```bash
# Bind to all interfaces
CODEFORGE_SERVER_HOST=0.0.0.0 codeforge serve

# Or set port
CODEFORGE_SERVER_HOST=0.0.0.0 CODEFORGE_SERVER_PORT=8327 codeforge serve
```

Access from another device: `http://<your-ip>:8327/v1/health`

**Security note:** When binding to `0.0.0.0`, the security proxy is still active. For LAN access, consider:
- Setting `CODEFORGE_SERVER_ALLOWED_ORIGINS` to your LAN subnet
- Using a firewall to restrict access to port 8327
- Keeping `CODEFORGE_SERVER_ENABLE_SECURITY=true`

## OpenAI Compatibility Status

| Feature | Status |
|---|---|
| `/v1/chat/completions` | Supported (via Ollama) |
| `/v1/completions` | Supported (via Ollama) |
| `/v1/models` | Supported |
| Streaming (SSE) | Supported |
| Function calling | Depends on model |
| Embeddings (`/v1/embeddings`) | Not implemented (501) |

The OpenAI-compatible endpoints proxy requests to Ollama's native OpenAI-compatible API. Model availability depends on what's installed locally via Ollama.
