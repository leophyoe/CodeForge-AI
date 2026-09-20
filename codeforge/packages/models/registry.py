"""Model registry for tracking known models."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .models import ModelMetadata, ModelStatus

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Stores metadata about known models using JSON persistence."""

    def __init__(self, registry_path: str | Path = "data/model_registry.json") -> None:
        self._path = Path(registry_path)
        self._models: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path) as f:
                    self._models = json.load(f)
            except Exception as e:
                logger.warning("Failed to load registry: %s", e)
                self._models = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._models, f, indent=2)

    def register(self, metadata: ModelMetadata) -> None:
        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "model_id": metadata.model_id,
            "name": metadata.name,
            "path": metadata.path,
            "provider": metadata.provider,
            "task": metadata.task.value,
            "architecture": metadata.architecture,
            "dtype": metadata.dtype,
            "parameter_count": metadata.parameter_count,
            "context_length": metadata.context_length,
            "quantization": metadata.quantization,
            "source": metadata.source,
            "license": metadata.license,
            "has_tokenizer": metadata.has_tokenizer,
            "format": metadata.format.value,
            "status": ModelStatus.DISCOVERED.value,
            "created_at": metadata.created_at or now,
            "updated_at": now,
        }
        self._models[metadata.model_id] = entry
        self._save()
        logger.info("Registered model '%s'", metadata.model_id)

    def unregister(self, model_id: str) -> bool:
        if model_id in self._models:
            del self._models[model_id]
            self._save()
            logger.info("Unregistered model '%s'", model_id)
            return True
        return False

    def get(self, model_id: str) -> dict | None:
        return self._models.get(model_id)

    def list_models(self) -> list[dict]:
        return list(self._models.values())

    def update_status(self, model_id: str, status: ModelStatus) -> bool:
        if model_id in self._models:
            self._models[model_id]["status"] = status.value
            self._models[model_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save()
            return True
        return False

    def exists(self, model_id: str) -> bool:
        return model_id in self._models

    def count(self) -> int:
        return len(self._models)
