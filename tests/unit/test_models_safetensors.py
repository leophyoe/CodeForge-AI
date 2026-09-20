"""Tests for safetensors inspection."""

from pathlib import Path

from codeforge.packages.models.safetensors_inspect import (
    format_size,
    inspect_safetensors_file,
)


class TestFormatSize:
    def test_bytes(self) -> None:
        assert format_size(100) == "100 B"

    def test_kilobytes(self) -> None:
        assert "KB" in format_size(2048)

    def test_megabytes(self) -> None:
        assert "MB" in format_size(2 * 1024 * 1024)

    def test_gigabytes(self) -> None:
        assert "GB" in format_size(2 * 1024 * 1024 * 1024)


class TestInspectSafetensors:
    def test_inspect_nonexistent(self) -> None:
        info = inspect_safetensors_file("/nonexistent/file.safetensors")
        assert info.tensor_count == 0

    def test_inspect_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.safetensors"
        f.touch()
        info = inspect_safetensors_file(f)
        assert info.tensor_count == 0

    def test_inspect_valid_safetensors(self, tmp_path: Path) -> None:
        try:
            import torch
            from safetensors.torch import save_file

            tensors = {
                "layer.weight": torch.randn(64, 64),
                "layer.bias": torch.randn(64),
            }
            f = tmp_path / "model.safetensors"
            save_file(tensors, str(f))
            info = inspect_safetensors_file(f)
            assert info.tensor_count == 2
            assert info.total_size_bytes > 0
            names = [t.name for t in info.tensors]
            assert "layer.weight" in names
        except ImportError:
            pass
