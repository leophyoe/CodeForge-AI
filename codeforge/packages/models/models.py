"""Data models for model management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ModelStatus(str, Enum):
    """Model lifecycle states."""

    DISCOVERED = "discovered"
    VALIDATED = "validated"
    LOADING = "loading"
    LOADED = "loaded"
    UNLOADING = "unloading"
    UNLOADED = "unloaded"
    FAILED = "failed"


class ModelFormat(str, Enum):
    """Supported model formats."""

    SAFETENSORS = "safetensors"
    PYTORCH_BIN = "pytorch_bin"
    PYTORCH_CHECKPOINT = "pytorch_checkpoint"
    HUGGINGFACE = "huggingface"
    UNKNOWN = "unknown"


class ModelTask(str, Enum):
    """Model task types."""

    CAUSAL_LM = "causal-lm"
    MASKED_LM = "masked-lm"
    SEQ2SEQ = "seq2seq"
    EMBEDDING = "embedding"
    CLASSIFICATION = "classification"
    UNKNOWN = "unknown"


@dataclass
class ModelMetadata:
    """Metadata about a model."""

    model_id: str = ""
    name: str = ""
    path: str = ""
    provider: str = "pytorch"
    task: ModelTask = ModelTask.UNKNOWN
    architecture: str = ""
    dtype: str = "auto"
    parameter_count: float | None = None
    context_length: int | None = None
    vocab_size: int | None = None
    quantization: str = "none"
    source: str = ""
    license: str = ""
    has_tokenizer: bool = False
    format: ModelFormat = ModelFormat.UNKNOWN
    config_exists: bool = False
    weight_files: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ModelConfig:
    """User-facing model configuration."""

    id: str = ""
    path: str = ""
    provider: str = "pytorch"
    task: str = "causal-lm"
    dtype: str = "auto"
    device: str = "auto"


@dataclass
class ModelInspection:
    """Detailed model inspection result."""

    model_id: str = ""
    name: str = ""
    provider: str = ""
    task: str = ""
    architecture: str = ""
    parameter_count: float | None = None
    parameter_count_str: str = "Unknown"
    dtype: str = ""
    context_length: int | None = None
    vocab_size: int | None = None
    quantization: str = ""
    tokenizer: str = "None"
    path: str = ""
    format: str = ""
    estimated_ram_gb: float = 0.0
    estimated_vram_gb: float = 0.0
    compatibility: str = ""
    status: str = ""
    weight_files: list[str] = field(default_factory=list)
    config_exists: bool = False

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "provider": self.provider,
            "task": self.task,
            "architecture": self.architecture,
            "parameter_count": self.parameter_count,
            "parameter_count_str": self.parameter_count_str,
            "dtype": self.dtype,
            "context_length": self.context_length,
            "vocab_size": self.vocab_size,
            "quantization": self.quantization,
            "tokenizer": self.tokenizer,
            "path": self.path,
            "format": self.format,
            "estimated_ram_gb": self.estimated_ram_gb,
            "estimated_vram_gb": self.estimated_vram_gb,
            "compatibility": self.compatibility,
            "status": self.status,
            "weight_files": self.weight_files,
            "config_exists": self.config_exists,
        }


@dataclass
class TensorInfo:
    """Information about a single tensor in a safetensors file."""

    name: str = ""
    dtype: str = ""
    shape: list[int] = field(default_factory=list)
    size_bytes: int = 0


@dataclass
class SafetensorsInfo:
    """Metadata from a safetensors file."""

    file_path: str = ""
    tensor_count: int = 0
    total_size_bytes: int = 0
    tensors: list[TensorInfo] = field(default_factory=list)


@dataclass
class GenerationResult:
    """Result from a generation call."""

    text: str = ""
    tokens: list[int] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict = field(default_factory=dict)


@dataclass
class StreamToken:
    """A single token from streaming generation."""

    text: str = ""
    token_id: int = 0
    is_end: bool = False
