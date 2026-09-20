"""Tests for the tiny test model."""

import json
from pathlib import Path

import pytest

from codeforge.packages.models.test_model import create_test_model

torch = pytest.importorskip("torch", reason="PyTorch not installed")


class TestCreateTestModel:
    def test_creates_model_files(self, tmp_path: Path) -> None:
        model_path = create_test_model(tmp_path / "test_model")
        assert model_path.exists()
        assert (model_path / "config.json").exists()
        assert (model_path / "tokenizer_config.json").exists()
        assert (model_path / "pytorch_model.bin").exists()

    def test_config_has_required_fields(self, tmp_path: Path) -> None:
        model_path = create_test_model(tmp_path / "test_model")
        with open(model_path / "config.json") as f:
            config = json.load(f)
        assert "architectures" in config
        assert "vocab_size" in config
        assert "hidden_size" in config

    def test_model_loadable(self, tmp_path: Path) -> None:
        model_path = create_test_model(tmp_path / "test_model")
        state_dict = torch.load(str(model_path / "pytorch_model.bin"), weights_only=True)
        assert isinstance(state_dict, dict)
        assert len(state_dict) > 0

    def test_idempotent(self, tmp_path: Path) -> None:
        p1 = create_test_model(tmp_path / "m1")
        p2 = create_test_model(tmp_path / "m1")
        assert p1 == p2
