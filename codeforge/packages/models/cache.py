"""Model instance caching to avoid duplicate loading."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ModelCache:
    """Tracks loaded model instances to prevent duplicates."""

    def __init__(self) -> None:
        self._loaded: dict[str, Any] = {}

    def add(self, model_id: str, instance: object) -> None:
        if model_id in self._loaded:
            logger.warning("Model '%s' already in cache, replacing", model_id)
        self._loaded[model_id] = instance
        logger.info("Cached model '%s'", model_id)

    def get(self, model_id: str) -> object | None:
        return self._loaded.get(model_id)

    def remove(self, model_id: str) -> bool:
        if model_id in self._loaded:
            del self._loaded[model_id]
            logger.info("Removed model '%s' from cache", model_id)
            return True
        return False

    def contains(self, model_id: str) -> bool:
        return model_id in self._loaded

    def list_loaded(self) -> list[str]:
        return list(self._loaded.keys())

    def clear(self) -> None:
        self._loaded.clear()

    def size(self) -> int:
        return len(self._loaded)
