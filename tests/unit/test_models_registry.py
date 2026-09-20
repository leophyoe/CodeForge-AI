"""Tests for ModelRegistry."""

from pathlib import Path

from codeforge.packages.models.models import ModelMetadata, ModelStatus
from codeforge.packages.models.registry import ModelRegistry


class TestModelRegistry:
    def _make_registry(self, tmp_path: Path) -> ModelRegistry:
        registry_path = tmp_path / "test_registry.json"
        return ModelRegistry(registry_path=registry_path)

    def test_register_and_get(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        meta = ModelMetadata(model_id="test-m", name="Test", path="/models/test")
        reg.register(meta)
        entry = reg.get("test-m")
        assert entry is not None
        assert entry["model_id"] == "test-m"

    def test_get_missing(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        assert reg.get("nonexistent") is None

    def test_unregister(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        meta = ModelMetadata(model_id="m1", path="/m1")
        reg.register(meta)
        assert reg.unregister("m1") is True
        assert reg.get("m1") is None
        assert reg.unregister("m1") is False

    def test_list_models(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        reg.register(ModelMetadata(model_id="m1", path="/m1"))
        reg.register(ModelMetadata(model_id="m2", path="/m2"))
        models = reg.list_models()
        assert len(models) == 2

    def test_exists(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        reg.register(ModelMetadata(model_id="m1", path="/m1"))
        assert reg.exists("m1") is True
        assert reg.exists("m2") is False

    def test_count(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        assert reg.count() == 0
        reg.register(ModelMetadata(model_id="m1", path="/m1"))
        assert reg.count() == 1

    def test_update_status(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        reg.register(ModelMetadata(model_id="m1", path="/m1"))
        assert reg.update_status("m1", ModelStatus.LOADED) is True
        entry = reg.get("m1")
        assert entry is not None
        assert entry["status"] == "loaded"
        assert reg.update_status("m2", ModelStatus.LOADED) is False

    def test_persistence(self, tmp_path: Path) -> None:
        registry_path = tmp_path / "persist.json"
        reg1 = ModelRegistry(registry_path=registry_path)
        reg1.register(ModelMetadata(model_id="m1", path="/m1"))

        reg2 = ModelRegistry(registry_path=registry_path)
        assert reg2.get("m1") is not None
