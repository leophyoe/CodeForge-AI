# CodeForge AI - Hardware Detection (Phase 1)

## Overview

Phase 1 implements the `HardwareManager` - a cross-platform hardware detection system that provides structured information about the host system's capabilities.

## What Was Implemented

### Core Package: `codeforge/packages/hardware/`

| Module | Purpose |
|--------|---------|
| `models.py` | Data classes: `HardwareInfo`, `CPUInfo`, `RAMInfo`, `GPUInfo`, `DiskInfo`, `PyTorchInfo` |
| `system.py` | OS, architecture, hostname, Python version detection |
| `cpu.py` | CPU model, cores, threads, frequency, flags (py-cpuinfo → psutil → platform fallback) |
| `ram.py` | Total, available, used RAM (psutil → /proc/meminfo → ctypes fallback) |
| `gpu.py` | GPU detection: NVIDIA (pynvml → PyTorch), AMD (rocminfo), Apple (MPS) |
| `disk.py` | Disk space detection via psutil |
| `pytorch_detect.py` | PyTorch version, CUDA, cuDNN, MPS detection |
| `manager.py` | `HardwareManager` class - main entry point with caching |

### CLI: `codeforge hardware`

```bash
codeforge hardware    # Display hardware info table
codeforge doctor      # Run diagnostics
```

### API: `GET /v1/hardware`

```bash
# Start server
uvicorn codeforge.apps.server.app:app --port 8420

# Query hardware
curl http://localhost:8420/v1/hardware
curl http://localhost:8420/v1/hardware/summary
curl http://localhost:8420/v1/hardware/compatibility
```

## Hardware Detection Methods

### CPU
1. **py-cpuinfo** (preferred) - Most detailed info
2. **psutil** - Fallback with basic info
3. **platform module** - Last resort

### RAM
1. **psutil** - Cross-platform
2. **/proc/meminfo** - Linux fallback
3. **ctypes (GlobalMemoryStatusEx)** - Windows fallback
4. **sysctl** - macOS fallback

### GPU
1. **nvidia-ml-py (pynvml)** - NVIDIA GPU details
2. **PyTorch CUDA** - NVIDIA via PyTorch
3. **rocminfo** - AMD GPU detection
4. **PyTorch MPS** - Apple Silicon

### Acceleration Backend Priority
```
NVIDIA + CUDA → CUDA
AMD + ROCm → ROCm
Apple Silicon + MPS → MPS
Otherwise → CPU
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_hardware_manager.py -v

# Run with coverage
pytest tests/ --cov=codeforge/packages/hardware
```

## Limitations

- CPU physical core count may show 0 on some Linux systems (depends on py-cpuinfo)
- AMD GPU VRAM detection requires rocminfo to be installed
- Apple Silicon VRAM is not reported (unified memory architecture)
- PyTorch is optional for Phase 1 - detection works without it

## Files Changed

```
codeforge/__init__.py
codeforge/cli.py
codeforge/packages/hardware/__init__.py
codeforge/packages/hardware/models.py
codeforge/packages/hardware/system.py
codeforge/packages/hardware/cpu.py
codeforge/packages/hardware/ram.py
codeforge/packages/hardware/gpu.py
codeforge/packages/hardware/disk.py
codeforge/packages/hardware/pytorch_detect.py
codeforge/packages/hardware/manager.py
codeforge/apps/server/__init__.py
codeforge/apps/server/app.py
codeforge/apps/server/routes.py
tests/unit/test_hardware_models.py
tests/unit/test_hardware_detection.py
tests/unit/test_hardware_manager.py
tests/unit/test_api_hardware.py
tests/unit/test_cli.py
pyproject.toml
environment.yml
.gitignore
.env.example
```
