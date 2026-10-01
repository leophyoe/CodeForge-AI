# Phase 11 — Agent Engine

An autonomous tool-using loop: the model plans, calls tools, observes
results, and iterates until it produces a final answer or the step budget
runs out.

## Package (`codeforge/packages/agent/`)

- `errors.py` — `AgentError` base; `AgentLLMError`, `AgentConfigError`,
  `AgentCancelledError`.
- `models.py` — `AgentConfig` (model_id, workspace_id, max_steps=10,
  max_tokens=512, temperature=0.2, allowed_tools, with `.validate()`),
  `AgentStatus` (`running|completed|failed|max_steps|cancelled`),
  `ToolCall`, `AgentStep` (kind `llm|tool`, text/arguments/success/error),
  `AgentResult` (steps, llm_calls, tool_calls, duration_s, `.to_dict()`).
- `parser.py` — `parse_tool_call(text)` extracts a `ToolCall` from the
  model output. Accepted forms:
  - ```` ```tool_call {"tool": ..., "arguments": {...}} ``` ```` (canonical),
  - ```` ```json {"tool": ..., "arguments": {...}} ``` ````,
  - bare JSON with `tool`/`name`/`tool_name` and
    `arguments`/`args`/`input`/`parameters` keys.
  Anything else → `None` (treated as the final answer);
  `extract_final_text()` strips tool fences for display.
- `prompt.py` — `build_system_prompt(tools, config)` renders the system
  message: workspace context, the tool-call protocol, every tool with its
  JSON input schema, and a restricted-set notice when `allowed_tools` is set.
- `session.py` — `AgentSession` (status, cancel flag, steps, timestamps;
  `cancel()` cooperatively flags a running session) and `AgentSessionStore`
  (thread-safe create/get/list/remove/clear, bounded — evicts *finished*
  sessions first when over `max_sessions`).
- `engine.py` — the core loop:
  - `LLMClient` protocol (`chat(messages, model_id, *, max_tokens,
    temperature) -> str`); `GenerationLLM` adapts `GenerationService`, any
    model manager can be plugged in, tests inject fakes via the same
    protocol.
  - Each turn: append system+history → `asyncio.to_thread(llm.chat)` →
    parse. If no tool call → `COMPLETED` with that text as `final_text`.
  - Tool calls execute through the shared `build_tool_manager()` policy
    layer (approval-gated tools still enforce their policy; `run_command`
    can never self-approve). Results are fed back to the model as
    `TOOL_RESULT <name>:\n{json}` user messages (including `error_code`
    on failure) so it can react.
  - Unknown/disallowed tools get a `TOOL_RESULT error:` feedback instead
    of aborting the loop.
  - Budget: `max_steps` exhausted → `MAX_STEPS` with the last model text.
  - Cancellation checked before every turn → `CANCELLED`.
  - LLM exceptions → `FAILED` with the error recorded on the result and
    first step. **`ModelNotLoadedError` re-raises** (the API maps it to
    409 so the client knows to load the model first).
  - The session object is finalized (status, timestamps) regardless of
    outcome.

## API

| Endpoint | Description |
|----------|-------------|
| `POST /v1/agent/run` | Run a task to completion: `{task, model, workspace_id?, max_steps?, max_tokens?, temperature?, allowed_tools?}` → `AgentResult.to_dict()` |
| `GET /v1/agent/tasks` | List session summaries (bounded store) |
| `GET /v1/agent/tasks/{id}` | Full result for one task → 404 if unknown/evicted |
| `DELETE /v1/agent/tasks/{id}` | Drop a session |
| `POST /v1/agent/tasks/{id}/cancel` | Flag a running session (`cancelled: false` if already finished) |
| `GET /v1/agent/health` | Engine status + registered tool count + live sessions |

Errors: 409 model not loaded, 422 invalid config, 404 unknown task.

## CLI

```bash
codeforge agent "Add docstrings to utils.py" -m tiny-random-gpt2 -w myws
codeforge agent "Summarize the repo" -m openai:gpt-4o-mini --allow read_file --allow search_code
```

The CLI auto-loads the model if needed, runs the engine, prints each step
(llm preview / `tool(args)` with ok|fail), then the status line and final
answer. Exit code is 0 only for `completed`.

## Tests

`tests/unit/test_agent.py` (34 tests) covers the parser variants, prompt
rendering, config validation, session store semantics, the engine loop
(final-only, tool→feedback→final, unknown tool, `allowed_tools` filtering,
max-steps exhaustion, cancellation, LLM failure, `ModelNotLoadedError`
re-raise, failed-tool recovery, result serialization), and the API surface
(run, tasks CRUD, cancel, 409/422/404, health). All tests use scripted
`FakeLLM` doubles — no network, no real models.
