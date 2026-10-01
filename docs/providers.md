# Remote Model Providers (OpenAI / Gemini / Local)

CodeForge AI supports interchangeable model backends selected by **model id prefix**:

| Model ID | Backend | Auth env |
|---|---|---|
| `tiny-random-gpt2`, `llama-3.1-8b-instruct`, ... | Local (PyTorch) | none |
| `openai:gpt-4o-mini`, `openai:gpt-4o` | OpenAI Chat Completions API | `OPENAI_API_KEY` |
| `gemini:gemini-2.5-flash` | Google Gemini generateContent API | `GEMINI_API_KEY` |

Local models require an explicit load (`POST /v1/models/{id}/load` or `codeforge model load`).
Remote models **auto-load** on first use — loading a remote model validates the credential.

## Configuration

All variables are read from the process environment or a `.env` file in the repo root.

```bash
OPENAI_API_KEY=sk-...              # or CODEFORGE_OPENAI_API_KEY (takes precedence)
GEMINI_API_KEY=...                 # or CODEFORGE_GEMINI_API_KEY
OPENAI_BASE_URL=https://api.openai.com/v1   # optional, for proxies/compatible servers
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta  # optional
```

Listing models with no key configured simply omits the corresponding remote entries.

## API

```bash
# List local + configured remote models
curl http://127.0.0.1:8000/v1/models

# Remote model detail (404 if provider not configured)
curl http://127.0.0.1:8000/v1/models/openai:gpt-4o-mini

# Optional explicit load (validates credentials)
curl -X POST http://127.0.0.1:8000/v1/models/openai:gpt-4o-mini/load -d '{}' -H 'Content-Type: application/json'

# Chat — same payload, swap the model id
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"model": "openai:gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}'
```

`/v1/chat`, `/v1/chat/completions`, `/v1/completions` and streaming variants all accept
`openai:` / `gemini:` ids. Usage tokens are computed by the remote API and passed through.

## CLI

```bash
codeforge model providers          # configured providers + endpoint/key status
codeforge model list               # local + remote model ids
codeforge chat -m "openai:gpt-4o-mini"
```

The VS Code extension model picker reads `/v1/models`, so remote models appear automatically.

## Behavior notes

- **Errors**: a remote API failure surfaces as a `finish_reason: "error"` result with the
  HTTP status in `usage.error`; chat endpoints return the message instead of hanging.
- **Usage**: `prompt_tokens` / `completion_tokens` come from the provider API (SSE
  `stream_options.include_usage` for OpenAI, `usageMetadata` for Gemini).
- **Isolation**: no real network calls happen at import time; credentials are only read
  when a remote model is loaded. Tests use `httpx.MockTransport` and never the network.

## Architecture

```
codeforge/packages/models/remote/
├── settings.py          # RemoteSettings (env/.env), cache reset for tests
├── base.py              # RemoteModelInstance, SSE parsing, make_client
├── openai_provider.py   # OpenAIProvider  (implements ModelProvider ABC)
├── gemini_provider.py   # GeminiProvider  (implements ModelProvider ABC)
└── catalog.py           # split_model_id / is_remote_model / provider registry
```

`GenerationService` and `ModelManager` dispatch on `is_remote_model(model_id)`; local
loading (`LocalPyTorchProvider`) is unchanged.
