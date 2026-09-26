"""SafeTensors file inspection without full model loading."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import SafetensorsInfo, TensorInfo

logger = logging.getLogger(__name__)


def inspect_safetensors_file(file_path: str | Path) -> SafetensorsInfo:
    """Inspect a safetensors file and return metadata without loading weights.

    Args:
        file_path: Path to the .safetensors file.

    Returns:
        SafetensorsInfo with tensor metadata.
    """
    path = Path(file_path)
    if not path.exists():
        return SafetensorsInfo(file_path=str(path))

    try:
        import safetensors  # noqa: F401

        return _inspect_with_safetensors_lib(path)
    except ImportError:
        return _inspect_with_manual_parsing(path)


def _inspect_with_safetensors_lib(path: Path) -> SafetensorsInfo:
    """Inspect using the safetensors library."""
    import safetensors

    try:
        header = safetensors.torch.load_file(str(path), device="cpu")
        tensors = []
        total_size = 0

        for name, tensor in header.items():
            dtype_str = str(tensor.dtype).replace("torch.", "")
            shape = list(tensor.shape)
            size_bytes = tensor.nelement() * tensor.element_size()
            total_size += size_bytes
            tensors.append(
                TensorInfo(
                    name=name,
                    dtype=dtype_str,
                    shape=shape,
                    size_bytes=size_bytes,
                )
            )

        return SafetensorsInfo(
            file_path=str(path),
            tensor_count=len(tensors),
            total_size_bytes=total_size,
            tensors=tensors,
        )
    except Exception as e:
        logger.debug("safetensors library inspection failed: %s", e)
        return _inspect_with_manual_parsing(path)


def _inspect_with_manual_parsing(path: Path) -> SafetensorsInfo:
    """Inspect by manually reading the header of a safetensors file.

    SafeTensors format: 8 bytes (header length) + header JSON + raw data.
    The header contains tensor metadata.
    """
    try:
        with open(path, "rb") as f:
            header_len_bytes = f.read(8)
            if len(header_len_bytes) < 8:
                return SafetensorsInfo(file_path=str(path))

            header_len = int.from_bytes(header_len_bytes, byteorder="little")
            if header_len <= 0 or header_len > 100_000_000:
                return SafetensorsInfo(file_path=str(path))

            header_bytes = f.read(header_len)
            if len(header_bytes) < header_len:
                return SafetensorsInfo(file_path=str(path))

            header = json.loads(header_bytes.decode("utf-8"))

            tensors = []
            total_size = 0

            dtype_map = {
                "F32": "float32",
                "F16": "float16",
                "BF16": "bfloat16",
                "I64": "int64",
                "I32": "int32",
                "I16": "int16",
                "I8": "int8",
                "U8": "uint8",
                "BOOL": "bool",
            }

            for name, info in header.items():
                if name == "__metadata__":
                    continue
                if not isinstance(info, dict):
                    continue

                dtype_raw = info.get("dtype", "")
                dtype = dtype_map.get(dtype_raw, dtype_raw)
                shape = info.get("shape", [])
                data_offsets = info.get("data_offsets", [0, 0])

                size_bytes = data_offsets[1] - data_offsets[0] if len(data_offsets) == 2 else 0

                total_size += size_bytes
                tensors.append(
                    TensorInfo(
                        name=name,
                        dtype=dtype or "",
                        shape=shape,
                        size_bytes=size_bytes,
                    )
                )

            return SafetensorsInfo(
                file_path=str(path),
                tensor_count=len(tensors),
                total_size_bytes=total_size,
                tensors=tensors,
            )

    except Exception as e:
        logger.debug("Manual safetensors parsing failed: %s", e)
        return SafetensorsInfo(file_path=str(path))


def format_size(size_bytes: int) -> str:
    """Format size in bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024**3:
        return f"{size_bytes / (1024**2):.1f} MB"
    return f"{size_bytes / (1024**3):.2f} GB"
