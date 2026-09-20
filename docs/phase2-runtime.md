# Phase 2: Python/PyTorch Environment Foundation

## Overview

Detects and manages the Python/PyTorch runtime: environment type, Python version, installed packages, device backends, memory, precision, and model estimation.

## Architecture

```
codeforge/packages/runtime/
├── models.py          # Pydantic data models
├── environment.py     # Python + conda/venv detection
├── pytorch_check.py   # PyTorch install + version + device detection
├── device.py          # DeviceManager: detect/select/fallback
├── backends.py        # RuntimeBackend ABC + CPU/CUDA/MPS
├── memory.py          # MemoryManager: system + GPU memory
├── precision.py       # PrecisionManager: dtype selection + validation
├── model_estimator.py # ModelMemoryEstimator: VRAM calculator
├── manager.py         # RuntimeManager: unified orchestration
└── __init__.py
```

## CLI Commands

| Command | Description |
|---|---|
| `codeforge runtime` | Show full runtime info (env, PyTorch, devices) |
| `codeforge device` | List all detected devices with status |
| `codeforge doctor` | System health check (enhanced with tensor test) |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/runtime` | Full runtime info |
| `GET` | `/v1/device` | Available devices |
| `GET` | `/v1/environment` | Python environment details |
| `POST` | `/v1/runtime/smoke-test` | Tensor smoke test on selected device |

## Key Features

- **Environment Detection**: Detects conda, venv, virtualenv, pipx, or system Python
- **Package Audit**: Lists installed ML packages and flags missing required dependencies
- **PyTorch Detection**: Version, CUDA version, cuDNN, ROCm/HIP, MPS support
- **Device Management**: Multi-device enumeration with automatic fallback (CUDA → MPS → CPU)
- **Memory Management**: System RAM + per-device GPU memory tracking
- **Precision Management**: Auto-selects best dtype (bfloat16, float16, float32) per device
- **Model Estimator**: Calculates VRAM requirements for a given model architecture

## Test Coverage

168 tests across 8 test files covering all runtime modules.
