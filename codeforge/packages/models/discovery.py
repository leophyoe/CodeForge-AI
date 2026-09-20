"""Model discovery - scan directories for local models."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .models import ModelFormat, ModelMetadata, ModelTask

logger = logging.getLogger(__name__)

HUGGINGFACE_CONFIG = "config.json"
SAFETENSORS_INDEX = "model.safetensors.index.json"
PYTORCH_BIN = "pytorch_model.bin"
PYTORCH_BIN_SHARD = "pytorch_model-00001-of-00002.bin"


def discover_models(model_dir: str | Path) -> list[ModelMetadata]:
    """Scan a directory for models and return metadata for each."""
    root = Path(model_dir)
    if not root.is_dir():
        return []

    models = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith(".") or entry.name.startswith("__"):
            continue

        metadata = _inspect_model_dir(entry)
        if metadata is not None:
            models.append(metadata)
            logger.info("Discovered model: %s at %s", metadata.model_id, metadata.path)

    return models


def _inspect_model_dir(path: Path) -> ModelMetadata | None:
    """Inspect a single model directory."""
    model_id = path.name
    name = model_id.replace("-", " ").replace("_", " ").title()

    fmt = _detect_format(path)
    if fmt == ModelFormat.UNKNOWN:
        return None

    config = _load_config(path)
    has_tokenizer = _detect_tokenizer(path)
    task = _detect_task(config)
    arch = _detect_architecture(config)
    param_count = _estimate_parameter_count(path, config)
    ctx_len = _get_config_value(
        config, ["max_position_embeddings", "n_positions", "max_sequence_length"]
    )
    vocab_size = _get_config_value(config, ["vocab_size"])
    weight_files = _list_weight_files(path)

    return ModelMetadata(
        model_id=model_id,
        name=name,
        path=str(path),
        provider="pytorch",
        task=task,
        architecture=arch,
        dtype="auto",
        parameter_count=param_count,
        context_length=ctx_len,
        vocab_size=vocab_size,
        has_tokenizer=has_tokenizer,
        format=fmt,
        config_exists=config is not None,
        weight_files=weight_files,
    )


def _detect_format(path: Path) -> ModelFormat:
    if (path / HUGGINGFACE_CONFIG).exists():
        has_safetensors = any(path.glob("*.safetensors"))
        has_bin = (path / PYTORCH_BIN).exists() or any(path.glob("pytorch_model-*.bin"))
        if has_safetensors or has_bin:
            return ModelFormat.HUGGINGFACE
        return ModelFormat.HUGGINGFACE

    safetensors_files = list(path.glob("*.safetensors"))
    if safetensors_files:
        return ModelFormat.SAFETENSORS

    pt_files = list(path.glob("*.pt"))
    if pt_files:
        return ModelFormat.PYTORCH_CHECKPOINT

    pth_files = list(path.glob("*.pth"))
    if pth_files:
        return ModelFormat.PYTORCH_BIN

    return ModelFormat.UNKNOWN


def _load_config(path: Path) -> dict | None:
    config_path = path / HUGGINGFACE_CONFIG
    if not config_path.exists():
        return None
    try:
        with open(config_path) as f:
            result: dict = json.load(f)
            return result
    except Exception:
        return None


def _detect_tokenizer(path: Path) -> bool:
    tokenizer_files = ["tokenizer.json", "tokenizer.model", "tokenizer_config.json"]
    return any((path / f).exists() for f in tokenizer_files)


def _detect_task(config: dict | None) -> ModelTask:
    if config is None:
        return ModelTask.UNKNOWN
    arch = config.get("architectures", [""])[0] if config.get("architectures") else ""
    arch_lower = arch.lower()
    if "causal" in arch_lower or "gpt" in arch_lower or "llama" in arch_lower:
        return ModelTask.CAUSAL_LM
    if "masked" in arch_lower or "bert" in arch_lower:
        return ModelTask.MASKED_LM
    if "seq2seq" in arch_lower or "t5" in arch_lower:
        return ModelTask.SEQ2SEQ
    return ModelTask.UNKNOWN


def _detect_architecture(config: dict | None) -> str:
    if config is None:
        return ""
    archs = config.get("architectures", [])
    return archs[0] if archs else ""


def _estimate_parameter_count(path: Path, config: dict | None) -> float | None:
    if config is not None:
        hidden = config.get("hidden_size")
        layers = config.get("num_hidden_layers")
        intermediate = config.get("intermediate_size")
        vocab = config.get("vocab_size")
        if all(v is not None for v in [hidden, layers, vocab]):
            assert hidden is not None  # noqa: S101
            assert layers is not None  # noqa: S101
            assert vocab is not None  # noqa: S101
            if intermediate is None:
                intermediate = hidden * 4
            embed = vocab * hidden
            attn = layers * (4 * hidden * hidden + 4 * hidden)
            ffn = layers * (2 * hidden * intermediate)
            lm_head = hidden * vocab
            total = embed + attn + ffn + lm_head
            return float(total)

    total_bytes = 0
    for f in path.glob("*.safetensors"):
        total_bytes += f.stat().st_size
    for f in path.glob("*.bin"):
        total_bytes += f.stat().st_size
    if total_bytes > 0:
        return float(total_bytes // 2)

    return None


def _get_config_value(config: dict | None, keys: list[str]) -> Any:
    if config is None:
        return None
    for key in keys:
        if key in config:
            return config[key]
    return None


def _list_weight_files(path: Path) -> list[str]:
    extensions = ["*.safetensors", "*.bin", "*.pt", "*.pth", "*.ckpt"]
    files = []
    for ext in extensions:
        for f in path.glob(ext):
            files.append(f.name)
    return sorted(files)
