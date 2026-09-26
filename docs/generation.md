# CodeForge AI - Generation (Phase 4)

Real text generation and streaming with token-by-token output.

## Architecture

```
codeforge/packages/generation/
  __init__.py        - Package exports
  errors.py          - Generation-specific error types
  schemas.py         - Data models (GenerationConfig, ChatMessage, etc.)
  context.py         - Tokenization and context length validation
  metrics.py         - Timing and token metrics
  streamer.py        - Token streaming with StreamEvents
  service.py         - GenerationService orchestrator
```

## Key Classes

### GenerationService
High-level service that orchestrates model loading and text generation.

```python
from codeforge.packages.generation import GenerationService, GenerationRequest, GenerationConfig

svc = GenerationService()

# Generate text
request = GenerationRequest(
    prompt="Write a hello world program",
    model_id="my-model",
    config=GenerationConfig(max_tokens=256, temperature=0.7),
)
response = svc.generate(request)
print(response.text)

# Chat
from codeforge.packages.generation import ChatMessage, ChatRequest

chat_req = ChatRequest(
    messages=[ChatMessage(role="user", content="Hello!")],
    model_id="my-model",
)
response = svc.chat(chat_req)
print(response.text)

# Streaming
for event in svc.stream_generate("Hello", "my-model"):
    if event.event_type.value == "token":
        print(event.text, end="", flush=True)
```

### GenerationConfig
Controls generation behavior:
- `max_tokens` (int): Maximum tokens to generate (1-32768, default 256)
- `temperature` (float): Sampling temperature (0.0-2.0, default 0.7)
- `top_p` (float): Top-p sampling (0.0-1.0, default 0.9)
- `top_k` (int): Top-k sampling (default 0 = disabled)
- `repetition_penalty` (float): Repetition penalty (default 1.0 = disabled)
- `stop_sequences` (list[str]): Stop generation on these sequences

### TokenStreamer
Wraps provider's `stream_generate` and yields `StreamEvent` objects:
- `StreamEventType.START` - Generation started
- `StreamEventType.TOKEN` - A token was generated
- `StreamEventType.END` - Generation completed
- `StreamEventType.ERROR` - An error occurred

### ContextManager
Handles tokenization and context length validation:
- Validates prompt fits within model context length
- Truncates text to fit if needed
- Formats chat messages into prompts

### GenerationMetrics
Tracks timing metrics:
- Time to first token (TTFT)
- Tokens per second
- Inter-token latency
- Total generation time

## CLI Commands

```bash
# Generate text
codeforge generate "Hello world" --model my-model --max-tokens 100

# Stream generation
codeforge generate "Hello world" --model my-model --stream

# Interactive chat
codeforge chat --model my-model

# Chat with streaming
codeforge chat --model my-model --stream
```

## Error Types

- `GenerationError` - Base error
- `ContextLengthExceededError` - Prompt too long
- `ModelNotLoadedError` - Model not loaded for generation
- `TokenizationError` - Tokenization failed
- `GenerationConfigError` - Invalid configuration
- `StreamTimeoutError` - Streaming timed out
- `ChatFormatError` - Invalid chat format

## Usage Tracking

Each `GenerationResponse` includes `UsageInfo`:
```python
{"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
```

## Integration with ModelManager

GenerationService uses ModelManager for model lifecycle:
1. Validates model is loaded
2. Gets provider from ModelManager
3. Gets model instance from cache
4. Calls provider's generate/stream_generate/chat methods
