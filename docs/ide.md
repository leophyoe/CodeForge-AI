# CodeForge AI — IDE API

Endpoints used by editor clients (Pulsar/Quanta IDE, VS Code). All paths are
prefixed with `/v1`, require the API key header when auth is enabled, and are
implemented in `codeforge/api/routers/ide.py` over `codeforge/packages/ide/`.

## Editor payload

Every request carries the same `editor` object:

```json
{
  "editor": {
    "file_path": "/abs/path/to/file.py",
    "language": "python",
    "workspace_id": "",
    "root_path": "/abs/path/to/repo",
    "selection": "selected text",
    "prefix": "text before the cursor",
    "suffix": "text after the cursor",
    "line": 12,
    "column": 4
  },
  "model": "tiny-random-gpt2",
  "settings": { "completion_max_tokens": 64 }
}
```

* `model` — optional. Falls back to `settings.model`, then the first registered model.
* `settings` — optional per-request `IDEConfig` overrides. Server-side
  `CODEFORGE_IDE_*` environment variables provide the base; client settings win.
* `root_path` / `file_path` are used to locate the workspace index when
  `workspace_id` is omitted.

## `POST /v1/ide/completions`

Inline completion for one cursor position.

```json
{ "editor": { "prefix": "def add(a, b):\n    ", "suffix": "\n", "language": "python" } }
```

Response:

```json
{ "text": "return a + b", "finish_reason": "stop", "usage": { }, "model_id": "…" }
```

Errors: `400` disabled by settings, `409` no model / model not loaded,
`422` invalid generation config.

## `POST /v1/ide/assist`

One of `explain`, `fix`, `refactor`, `tests`.

```json
{ "action": "explain", "editor": { "selection": "…" }, "include_workspace": true }
```

Response: `{ "action", "text", "finish_reason", "usage", "model_id", "prompt_chars" }`.

With `"stream": true` the response is `text/event-stream` SSE carrying
`{"type":"token","text":…}`, a final `{"type":"end",…}` and `[DONE]`.

`422` for an unknown action.

## `POST /v1/ide/context`

Gathers editor state plus index-derived chunks/symbols for a chat message.

```json
{ "editor": { "…": "…" }, "query": "optional search text", "max_chars": 8000 }
```

Response:

```json
{
  "workspace_id": "…",
  "context": "## File\n…",
  "chunks": [ { "chunk_id": "…", "content": "…", "relative_path": "…" } ],
  "symbols": [ { "name": "…", "kind": "function", "start_line": 0 } ],
  "results": [ ],
  "editor": { "has_selection": true, "line": 1, "column": 0 }
}
```

`context` is the pre-rendered prompt block; `chunks`/`symbols` are returned for
clients that want to render their own citation chips.

## `POST /v1/ide/index`

Create or refresh the workspace index (auto-index on connect).

```json
{ "root": "/abs/path/to/repo", "force": false, "background": true }
```

Response: `{ "workspace_id", "root_path", "index_status", "job", "stats" }`.
`job` is `null` when the index was already fresh and `force` was not set.
Errors: `403` path outside allowed roots, `400` indexing failure, `422` when
neither `root` nor `workspace_id` is supplied.

## `GET /v1/ide/status`

```json
{
  "server": "codeforge",
  "config": { "…": "IDEConfig" },
  "model": "tiny-random-gpt2",
  "workspaces": [ { "workspace_id": "…", "root_path": "…", "index_status": "READY" } ],
  "actions": ["explain", "fix", "refactor", "tests"]
}
```

## Configuration

| Setting | Default | Description |
|---|---|---|
| `server_url` | `http://127.0.0.1:8000` | Reported to the client |
| `model` | `""` | Preferred model id |
| `request_timeout` | `60` | Client-side timeout (seconds) |
| `completion_enabled` | `true` | Toggle inline completion |
| `completion_max_tokens` | `64` | Completion length |
| `completion_max_prefix_chars` | `2000` | Prefix window (tail kept) |
| `completion_max_suffix_chars` | `500` | Suffix window (head kept) |
| `chat_max_context_chars` | `8000` | Rendered context cap |
| `context_max_chunks` | `8` | Chunks returned per request |
| `context_max_symbols` | `40` | Symbols returned per request |
| `assist_max_tokens` | `512` | Assist answer length |
| `assist_temperature` | `0.3` | Assist sampling temperature |
| `auto_index` | `true` | Index on client connect |

Set any of them via `CODEFORGE_IDE_<NAME_UPPER>` or per request via `settings`.

## Notes

* Completions use a fill-in-the-middle prompt: the suffix is emitted before the
  prefix so a causal model keeps generating from the cursor.
* Raw model output is normalised by `clean_completion()` — markdown fences are
  removed, generation stops at the first stop sequence, and an echoed copy of
  the suffix's first line is dropped.
* The generation API exposes only `prompt` (no prefix/suffix pair), so the FIM
  contract lives in `codeforge/packages/ide/completions.py`.
