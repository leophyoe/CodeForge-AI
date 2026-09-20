# Phase 3: Model Runtime and Model Loading

## Overview

Builds a production-quality local model runtime for discovering, inspecting, validating, loading, and unloading models. Supports HuggingFace, SafeTensors, and PyTorch checkpoint formats.

## Architecture

```
codeforge/packages/models/
├── models.py              # Data models (ModelMetadata, ModelStatus, etc.)
├── provider.py            # ModelProvider ABC + LocalPyTorchProvider
├── manager.py             # ModelManager - main orchestration
├── registry.py            # ModelRegistry - persistent metadata store
├── cache.py               # ModelCache - loaded instance tracking
├── tokenizer.py           # TokenizerManager - separate tokenizer loading
├── discovery.py           # Model directory scanning
├── errors.py              # Structured error types
├── safetensors_inspect.py # SafeTensors metadata inspection
├── test_model.py          # Tiny test model for testing
└── __init__.py
```

## Supported Formats

| Format | Detection | Loading |
|--------|-----------|---------|
| HuggingFace | config.json + weight files | transformers.AutoModelForCausalLM |
| SafeTensors | *.safetensors files | safetensors.torch.load_file |
| PyTorch Checkpoint | *.pt, *.pth files | torch.load |

## CLI Commands

| Command | Description |
|---------|-------------|
| `codeforge models` | List all registered models |
| `codeforge model list` | List all registered models |
| `codeforge model inspect <id>` | Detailed model inspection |
| `codeforge model load <id>` | Load a model into memory |
| `codeforge model unload <id>` | Unload a model from memory |
| `codeforge model status` | Show loaded model status |
| `codeforge model discover` | Scan model directory |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/models` | List all models |
| GET | `/v1/models/{id}` | Get model details |
| GET | `/v1/models/{id}/status` | Get model status |
| POST | `/v1/models/{id}/load` | Load a model |
| POST | `/v1/models/{id}/unload` | Unload a model |

## Model Lifecycle

```
DISCOVERED → VALIDATED → LOADING → LOADED → UNLOADING → UNLOADED
                    ↓
                 FAILED
```

## Configuration

- `CODEFORGE_MODEL_DIR`: Model storage directory (default: `models/`)
- Models are discovered by scanning subdirectories for config.json or weight files

## Memory Validation

Before loading, the system:
1. Inspects model metadata
2. Estimates memory requirements
3. Checks available system memory
4. Warns or rejects if insufficient

Use `--force` to bypass memory checks.

## Test Model

A tiny transformer model (`TinyTransformer`) is included for testing:
- 256 vocab size, 32 hidden size, 2 layers
- ~100K parameters
- Runs on CPU
- Created automatically by `create_test_model()`

## Security

- Model paths are validated to prevent path traversal
- Only directories within the configured model directory are scanned
- No automatic model downloads
