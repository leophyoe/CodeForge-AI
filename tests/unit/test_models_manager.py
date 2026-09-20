"""Tests for ModelManager."""

import json
from pathlib import Path

from codeforge.packages.models.errors import ModelNotFoundError
from codeforge.packages.models.manager import ModelManager
from codeforge.packages.models.models import ModelStatus


class TestModelManager:
    def _setup_manager(self, tmp_path: Path) -> ModelManager:
        model_dir = tmp_path / "models"
        model_dir.mkdir()
        from codeforge.packages.models.registry import ModelRegistry
        registry = ModelRegistry(registry_path=tmp_path / "test_registry.json")
        manager = ModelManager(model_dir=model_dir)
        manager._registry = registry  # noqa: SLF001
        return manager

    def _create_test_model(self, model_dir: Path, name: str = "test-model") -> Path:
        model_path = model_dir / name
        model_path.mkdir()
        config = {"architectures": ["TinyTransformer"], "vocab_size": 256, "hidden_size": 32}
        with open(model_path / "config.json", "w") as f:
            json.dump(config, f)
        (model_path / "model.safetensors").touch()
        (model_path / "tokenizer.json").touch()
        return model_path

    def test_list_models_empty(self, tmp_path: Path) -> None:
        mm = self._setup_manager(tmp_path)
        assert mm.list_models() == []

    def test_discover_models(self, tmp_path: Path) -> None:
        mm = self._setup_manager(tmp_path)
        self._create_test_model(mm.model_dir)
        models = mm.discover_models()
        assert len(models) == 1
        assert models[0].model_id == "test-model"

    def test_register_model(self, tmp_path: Path) -> None:
        mm = self._setup_manager(tmp_path)
        model_path = self._create_test_model(mm.model_dir)
        meta = mm.register_model("custom-id", model_path)
        assert meta.model_id == "custom-id"

    def test_inspect_model(self, tmp_path: Path) -> None:
        mm = self._setup_manager(tmp_path)
        self._create_test_model(mm.model_dir)
        mm.discover_models()
        info = mm.inspect_model("test-model")
        assert info.model_id == "test-model"
        assert info.name != ""

    def test_inspect_missing_model(self, tmp_path: Path) -> None:
        mm = self._setup_manager(tmp_path)
        try:
            mm.inspect_model("nonexistent")
            raise AssertionError("Should have raised")
        except ModelNotFoundError:
            pass

    def test_get_model_status(self, tmp_path: Path) -> None:
        mm = self._setup_manager(tmp_path)
        self._create_test_model(mm.model_dir)
        mm.discover_models()
        assert mm.get_model_status("test-model") == ModelStatus.DISCOVERED

    def test_get_loaded_models(self, tmp_path: Path) -> None:
        mm = self._setup_manager(tmp_path)
        assert mm.get_loaded_models() == []

    def test_remove_model(self, tmp_path: Path) -> None:
        mm = self._setup_manager(tmp_path)
        self._create_test_model(mm.model_dir)
        mm.discover_models()
        assert mm.remove_model("test-model") is True
        assert mm.remove_model("test-model") is False

    def test_model_dir_property(self, tmp_path: Path) -> None:
        mm = self._setup_manager(tmp_path)
        assert mm.model_dir.exists()
