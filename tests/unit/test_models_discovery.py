"""Tests for model discovery."""

import json
from pathlib import Path

from codeforge.packages.models.discovery import (
    _detect_format,
    _load_config,
    discover_models,
)
from codeforge.packages.models.models import ModelFormat


class TestDiscovery:
    def test_discover_empty_dir(self, tmp_path: Path) -> None:
        models = discover_models(tmp_path)
        assert models == []

    def test_discover_nonexistent_dir(self) -> None:
        models = discover_models("/nonexistent/path")
        assert models == []

    def test_discover_huggingface_model(self, tmp_path: Path) -> None:
        model_dir = tmp_path / "test-hf-model"
        model_dir.mkdir()
        config = {"architectures": ["GPT2LMHeadModel"], "vocab_size": 50257}
        with open(model_dir / "config.json", "w") as f:
            json.dump(config, f)
        Path(model_dir / "pytorch_model.bin").touch()

        models = discover_models(tmp_path)
        assert len(models) == 1
        assert models[0].model_id == "test-hf-model"
        assert models[0].format == ModelFormat.HUGGINGFACE

    def test_discover_safetensors_model(self, tmp_path: Path) -> None:
        model_dir = tmp_path / "test-st-model"
        model_dir.mkdir()
        Path(model_dir / "model.safetensors").touch()

        models = discover_models(tmp_path)
        assert len(models) == 1
        assert models[0].format == ModelFormat.SAFETENSORS

    def test_discover_pt_checkpoint(self, tmp_path: Path) -> None:
        model_dir = tmp_path / "test-pt-model"
        model_dir.mkdir()
        Path(model_dir / "model.pt").touch()

        models = discover_models(tmp_path)
        assert len(models) == 1
        assert models[0].format == ModelFormat.PYTORCH_CHECKPOINT

    def test_skip_hidden_dirs(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        config = {"architectures": ["Test"]}
        with open(hidden / "config.json", "w") as f:
            json.dump(config, f)

        models = discover_models(tmp_path)
        assert len(models) == 0

    def test_detect_format_huggingface(self, tmp_path: Path) -> None:
        d = tmp_path / "hf"
        d.mkdir()
        (d / "config.json").touch()
        assert _detect_format(d) == ModelFormat.HUGGINGFACE

    def test_detect_format_safetensors(self, tmp_path: Path) -> None:
        d = tmp_path / "st"
        d.mkdir()
        (d / "model.safetensors").touch()
        assert _detect_format(d) == ModelFormat.SAFETENSORS

    def test_detect_format_unknown(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        assert _detect_format(d) == ModelFormat.UNKNOWN

    def test_load_config(self, tmp_path: Path) -> None:
        config = {"vocab_size": 100}
        with open(tmp_path / "config.json", "w") as f:
            json.dump(config, f)
        loaded = _load_config(tmp_path)
        assert loaded is not None
        assert loaded["vocab_size"] == 100

    def test_load_config_missing(self, tmp_path: Path) -> None:
        loaded = _load_config(tmp_path)
        assert loaded is None

    def test_tokenizer_detection(self, tmp_path: Path) -> None:
        model_dir = tmp_path / "with_tok"
        model_dir.mkdir()
        config = {"architectures": ["Test"]}
        with open(model_dir / "config.json", "w") as f:
            json.dump(config, f)
        (model_dir / "tokenizer.json").touch()

        models = discover_models(tmp_path)
        assert len(models) == 1
        assert models[0].has_tokenizer is True
