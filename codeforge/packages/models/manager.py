"""ModelManager - main orchestration for model operations."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .cache import ModelCache
from .discovery import discover_models
from .errors import (
    InsufficientMemoryError,
    ModelAlreadyLoadedError,
    ModelNotFoundError,
)
from .models import ModelInspection, ModelMetadata, ModelStatus
from .provider import LocalPyTorchProvider, ModelProvider
from .registry import ModelRegistry
from .tokenizer import TokenizerManager

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = os.environ.get("CODEFORGE_MODEL_DIR", "models")


class ModelManager:
    """Manages the full lifecycle of models."""

    def __init__(
        self,
        model_dir: str | Path = DEFAULT_MODEL_DIR,
        provider: ModelProvider | None = None,
    ) -> None:
        self._model_dir = Path(model_dir)
        self._provider = provider or LocalPyTorchProvider()
        self._registry = ModelRegistry()
        self._cache = ModelCache()
        self._tokenizer_mgr = TokenizerManager()
        self._statuses: dict[str, ModelStatus] = {}

    @property
    def model_dir(self) -> Path:
        return self._model_dir

    def list_models(self) -> list[dict]:
        """List all known models."""
        return self._registry.list_models()

    def register_model(self, model_id: str, path: str | Path) -> ModelMetadata:
        """Register a model from a directory path.

        If model_id is provided, it overrides the auto-detected ID.
        """
        model_path = Path(path)
        if not model_path.is_dir():
            raise ValueError(f"Path is not a directory: {model_path}")

        discovered = discover_models(self._model_dir)
        for m in discovered:
            if m.path == str(model_path.resolve()):
                if model_id:
                    m = ModelMetadata(
                        model_id=model_id,
                        name=model_id.replace("-", " ").replace("_", " ").title(),
                        path=m.path,
                        provider=m.provider,
                        task=m.task,
                        architecture=m.architecture,
                        dtype=m.dtype,
                        parameter_count=m.parameter_count,
                        context_length=m.context_length,
                        vocab_size=m.vocab_size,
                        has_tokenizer=m.has_tokenizer,
                        format=m.format,
                        config_exists=m.config_exists,
                        weight_files=m.weight_files,
                    )
                self._registry.register(m)
                self._statuses[m.model_id] = ModelStatus.DISCOVERED
                return m

        model_id_to_use = model_id or model_path.name
        metadata = ModelMetadata(
            model_id=model_id_to_use,
            name=model_id_to_use.replace("-", " ").replace("_", " ").title(),
            path=str(model_path),
        )
        self._registry.register(metadata)
        self._statuses[metadata.model_id] = ModelStatus.DISCOVERED
        return metadata

    def remove_model(self, model_id: str) -> bool:
        """Remove a model from the registry."""
        if self._cache.contains(model_id):
            self.unload_model(model_id)
        self._statuses.pop(model_id, None)
        return self._registry.unregister(model_id)

    def inspect_model(self, model_id: str) -> ModelInspection:
        """Get detailed inspection of a model."""
        entry = self._registry.get(model_id)
        if entry is None:
            raise ModelNotFoundError(model_id)

        metadata = _dict_to_metadata(entry)
        memory = self._provider.estimate_memory(metadata)
        compat = self._check_compatibility(metadata)
        status = self._statuses.get(model_id, ModelStatus.DISCOVERED)

        return ModelInspection(
            model_id=metadata.model_id,
            name=metadata.name,
            provider=metadata.provider,
            task=metadata.task.value,
            architecture=metadata.architecture,
            parameter_count=metadata.parameter_count,
            parameter_count_str=_format_params(metadata.parameter_count),
            dtype=metadata.dtype,
            context_length=metadata.context_length,
            vocab_size=metadata.vocab_size,
            quantization=metadata.quantization,
            tokenizer="Available" if metadata.has_tokenizer else "None",
            path=metadata.path,
            format=metadata.format.value,
            estimated_ram_gb=memory.get("total_gb", 0),
            estimated_vram_gb=memory.get("total_gb", 0),
            compatibility=compat,
            status=status.value,
            weight_files=metadata.weight_files,
            config_exists=metadata.config_exists,
        )

    def discover_models(self) -> list[ModelMetadata]:
        """Scan the model directory and register all found models."""
        models = discover_models(self._model_dir)
        for m in models:
            if not self._registry.exists(m.model_id):
                self._registry.register(m)
                self._statuses[m.model_id] = ModelStatus.DISCOVERED
        return models

    def load_model(
        self,
        model_id: str,
        device: str = "auto",
        dtype: str = "auto",
        force: bool = False,
    ) -> dict:
        """Load a model into memory."""
        if self._cache.contains(model_id) and not force:
            raise ModelAlreadyLoadedError(model_id)

        entry = self._registry.get(model_id)
        if entry is None:
            raise ModelNotFoundError(model_id)

        metadata = _dict_to_metadata(entry)
        self._statuses[model_id] = ModelStatus.VALIDATED

        memory = self._provider.estimate_memory(metadata)
        self._validate_memory(model_id, memory, force)

        self._statuses[model_id] = ModelStatus.LOADING
        try:
            instance = self._provider.load_model(metadata, device, dtype)
            self._cache.add(model_id, instance)
            self._statuses[model_id] = ModelStatus.LOADED
            self._registry.update_status(model_id, ModelStatus.LOADED)
            info = self._provider.get_model_info(instance)
            return {"model_id": model_id, "status": "loaded", **info}
        except Exception:
            self._statuses[model_id] = ModelStatus.FAILED
            self._registry.update_status(model_id, ModelStatus.FAILED)
            raise

    def unload_model(self, model_id: str) -> dict:
        """Unload a model from memory."""
        instance = self._cache.get(model_id)
        if instance is None:
            raise ModelNotFoundError(model_id)

        self._statuses[model_id] = ModelStatus.UNLOADING
        try:
            self._provider.unload_model(instance)
            self._cache.remove(model_id)
            entry = self._registry.get(model_id)
            if entry is not None:
                self._tokenizer_mgr.unload_tokenizer(Path(entry["path"]))
            self._statuses[model_id] = ModelStatus.UNLOADED
            self._registry.update_status(model_id, ModelStatus.UNLOADED)
            return {"model_id": model_id, "status": "unloaded"}
        except Exception:
            self._statuses[model_id] = ModelStatus.FAILED
            raise

    def get_loaded_models(self) -> list[str]:
        return self._cache.list_loaded()

    def get_model_status(self, model_id: str) -> ModelStatus:
        return self._statuses.get(model_id, ModelStatus.DISCOVERED)

    def get_provider(self) -> ModelProvider:
        return self._provider

    def get_registry(self) -> ModelRegistry:
        return self._registry

    def get_cache(self) -> ModelCache:
        return self._cache

    def get_tokenizer_manager(self) -> TokenizerManager:
        return self._tokenizer_mgr

    def _check_compatibility(self, metadata: ModelMetadata) -> str:
        issues = []
        if not metadata.config_exists:
            issues.append("No config.json")
        if not metadata.weight_files:
            issues.append("No weight files found")
        if not metadata.has_tokenizer:
            issues.append("No tokenizer found")
        if metadata.format.value == "unknown":
            issues.append("Unknown model format")
        return "Compatible" if not issues else "; ".join(issues)

    def _validate_memory(self, model_id: str, memory: dict, force: bool) -> None:
        if force:
            return
        try:
            from codeforge.packages.runtime import MemoryManager

            mm = MemoryManager()
            sys_mem = mm.get_system_memory()
            available_gb = sys_mem.available_gb
            required_gb = memory.get("total_gb", 0)
            if required_gb > 0 and available_gb > 0 and required_gb > available_gb * 0.9:
                raise InsufficientMemoryError(model_id, required_gb, available_gb)
        except ImportError:
            logger.debug("MemoryManager not available, skipping memory validation")
        except InsufficientMemoryError:
            raise


def _dict_to_metadata(d: dict) -> ModelMetadata:
    from .models import ModelFormat, ModelTask

    task_str = d.get("task", "unknown")
    try:
        task = ModelTask(task_str)
    except ValueError:
        task = ModelTask.UNKNOWN
    fmt_str = d.get("format", "unknown")
    try:
        fmt = ModelFormat(fmt_str)
    except ValueError:
        fmt = ModelFormat.UNKNOWN
    return ModelMetadata(
        model_id=d.get("model_id", ""),
        name=d.get("name", ""),
        path=d.get("path", ""),
        provider=d.get("provider", "pytorch"),
        task=task,
        architecture=d.get("architecture", ""),
        dtype=d.get("dtype", "auto"),
        parameter_count=d.get("parameter_count"),
        context_length=d.get("context_length"),
        quantization=d.get("quantization", "none"),
        source=d.get("source", ""),
        license=d.get("license", ""),
        has_tokenizer=d.get("has_tokenizer", False),
        format=fmt,
        config_exists=d.get("config_exists", False),
        weight_files=d.get("weight_files", []),
    )


def _format_params(count: float | None) -> str:
    if count is None:
        return "Unknown"
    if count >= 1e9:
        return f"{count / 1e9:.2f}B"
    if count >= 1e6:
        return f"{count / 1e6:.2f}M"
    if count >= 1e3:
        return f"{count / 1e3:.2f}K"
    return str(int(count))
