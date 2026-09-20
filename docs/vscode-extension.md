# CodeForge AI - VS Code Extension

A local-first AI coding assistant VS Code extension powered by CodeForge.

## Architecture

```
VS Code
   │
   ▼
CodeForge VS Code Extension (TypeScript)
   │
   │ HTTP / SSE
   ▼
CodeForge Local API (FastAPI)
   │
   ▼
GenerationService
   │
   ▼
LocalPyTorchProvider
   │
   ▼
Local AI Model
```

The extension is a **client**. All AI inference runs on the CodeForge server.

## Installation

### Local Development

```bash
cd codeforge-vscode
npm install
npm run compile
```

Then:
1. Open VS Code
2. Press `F5` to launch Extension Development Host
3. The extension activates automatically

### Packaging

```bash
npm install -g @vscode/vsce
cd codeforge-vscode
vsce package
```

Install the `.vsix` file via VS Code Extensions view.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `codeforge.server.url` | `http://127.0.0.1:8000` | CodeForge API server URL |
| `codeforge.model` | `""` | Selected model ID |
| `codeforge.requestTimeout` | `60` | Request timeout (seconds) |
| `codeforge.enableInlineCompletion` | `true` | Enable inline code completion |
| `codeforge.enableChat` | `true` | Enable chat interface |
| `codeforge.enableCodeActions` | `true` | Enable code actions |
| `codeforge.enableTelemetry` | `false` | Enable anonymous telemetry |
| `codeforge.completion.debounceMs` | `300` | Completion debounce delay |
| `codeforge.completion.maxPrefixChars` | `2000` | Max prefix for completion |
| `codeforge.completion.maxSuffixChars` | `500` | Max suffix for completion |
| `codeforge.completion.maxTokens` | `256` | Max tokens for completion |
| `codeforge.chat.maxContextChars` | `8000` | Max context for chat |
| `codeforge.debug` | `false` | Enable debug logging |

## Commands

| Command | Description |
|---------|-------------|
| `CodeForge: Open Chat` | Open the chat panel |
| `CodeForge: Explain Code` | Explain selected code |
| `CodeForge: Generate Code` | Generate code from instruction |
| `CodeForge: Fix Code` | Fix bugs in selected code |
| `CodeForge: Refactor Code` | Refactor selected code |
| `CodeForge: Generate Tests` | Generate unit tests |
| `CodeForge: Select Model` | Choose a model |
| `CodeForge: Check Connection` | Test server connection |
| `CodeForge: Server Information` | Show server details |
| `CodeForge: Set API Key` | Store API key securely |
| `CodeForge: Clear API Key` | Remove stored API key |

## API Key Storage

API keys are stored using VS Code `SecretStorage`:

1. Run `CodeForge: Set API Key`
2. Enter your key
3. Key is encrypted and stored by VS Code

API keys are **never** stored in:
- settings.json
- workspace files
- source code
- logs

## Chat Interface

The chat panel supports:
- User and assistant messages
- Streaming responses (SSE)
- Cancellation
- Code block rendering
- Markdown formatting

Open with `CodeForge: Open Chat` or click the status bar item.

## Inline Completion

Type in any file to trigger completions. The extension:
- Sends prefix/suffix context to the CodeForge API
- Returns single-line completions
- Supports debouncing and cancellation

Configure via:
- `codeforge.enableInlineCompletion` - Enable/disable
- `codeforge.completion.debounceMs` - Debounce delay
- `codeforge.completion.maxTokens` - Max completion length

## Code Actions

Select code and right-click for context menu:
- Explain with CodeForge
- Fix with CodeForge
- Refactor with CodeForge
- Generate Tests with CodeForge

Or use Command Palette commands.

## LAN Usage

To connect to a CodeForge server on another machine:

1. On the server machine, start with:
   ```bash
   codeforge serve --host 0.0.0.0
   ```

2. In VS Code, set:
   ```json
   {
     "codeforge.server.url": "http://192.168.1.100:8000"
   }
   ```

3. Consider setting up API key authentication for LAN access.

### Security Notes

- Default binding is `127.0.0.1` (localhost only)
- Binding to `0.0.0.0` exposes to LAN
- Use API keys for authentication
- Configure firewall appropriately

## Privacy

CodeForge is **local-first**:
- VS Code → Local CodeForge server → Local AI model
- No external cloud AI
- No telemetry by default
- No code/prompt collection

## Error Handling

The extension handles:
- Connection refused
- Request timeout
- 401 Unauthorized
- 404 Not Found
- 409 Conflict
- 429 Rate Limited
- 500 Server Error

Errors are shown via VS Code notifications.

## Status Bar

The status bar shows connection state:
- `$(check) CodeForge: Connected` - Server online
- `$(sync~spin) CodeForge: Connecting...` - Connecting
- `$(circle-slash) CodeForge: Offline` - Server unreachable
- `$(sync~spin) CodeForge: Loading Model...` - Model loading

Click to check connection.

## Output Channel

View logs via: View → Output → CodeForge

Enable debug logging with `codeforge.debug: true`.

## Architecture Details

### Files

```
codeforge-vscode/
├── package.json           # Extension manifest
├── tsconfig.json          # TypeScript config
├── src/
│   ├── extension.ts       # Activation/deactivation
│   ├── api/
│   │   ├── client.ts      # HTTP API client
│   │   ├── types.ts       # TypeScript interfaces
│   │   ├── errors.ts      # Error classes
│   │   └── streaming.ts   # SSE stream reader
│   ├── chat/
│   │   └── chatController.ts  # Chat WebviewView
│   ├── completion/
│   │   └── completionProvider.ts  # Inline completion
│   ├── commands/
│   │   └── index.ts       # All command implementations
│   ├── configuration/
│   │   └── config.ts      # Configuration reader
│   ├── context/
│   │   └── workspaceContext.ts  # Editor context utilities
│   ├── status/
│   │   └── statusBar.ts   # Status bar management
│   └── utils/
│       ├── helpers.ts     # General utilities
│       └── outputChannel.ts  # Output channel
└── test/
    └── unit/
        ├── helpers.test.ts
        ├── streaming.test.ts
        └── apiClient.test.ts
```

### Dependencies

- VS Code Extension API
- Node.js (runtime)
- TypeScript (compile)

No external npm dependencies required.

## Limitations

- No actual model loading in the extension
- No repository indexing (Phase 7)
- No agent tools (Phase 9+)
- No RAG (Phase 8+)
- No file modification automation
- No terminal execution
- No Git integration

## Troubleshooting

### "Cannot connect to server"

1. Check if CodeForge server is running: `codeforge serve`
2. Verify server URL in settings
3. Check firewall rules for LAN

### "Authentication failed"

1. Set API key: `CodeForge: Set API Key`
2. Ensure server requires auth

### "No model selected"

1. Run `CodeForge: Select Model`
2. Ensure server has models available

### Completions not appearing

1. Check `codeforge.enableInlineCompletion` is true
2. Ensure model is selected
3. Check server connection
