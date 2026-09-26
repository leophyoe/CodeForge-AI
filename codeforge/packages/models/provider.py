"""Model provider interface and PyTorch implementation."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .errors import ModelLoadError, ModelUnloadError
from .models import GenerationResult, ModelMetadata, StreamToken

logger = logging.getLogger(__name__)


def _format_parameter_count(count: int) -> str:
    if count >= 1e9:
        return f"{count / 1e9:.2f}B"
    if count >= 1e6:
        return f"{count / 1e6:.2f}M"
    if count >= 1e3:
        return f"{count / 1e3:.2f}K"
    return str(count)


class ModelProvider(ABC):
    """Abstract interface for model providers."""

    @abstractmethod
    def load_model(
        self, metadata: ModelMetadata, device: str = "auto", dtype: str = "auto"
    ) -> object:
        """Load a model and return the model instance."""

    @abstractmethod
    def unload_model(self, model_instance: object) -> None:
        """Unload a model and free resources."""

    @abstractmethod
    def is_loaded(self, model_instance: object) -> bool:
        """Check if a model is currently loaded."""

    @abstractmethod
    def generate(
        self,
        model_instance: object,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> GenerationResult:
        """Generate text from a prompt."""

    @abstractmethod
    def stream_generate(
        self,
        model_instance: object,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> Any:
        """Stream generate tokens. Yields StreamToken."""

    @abstractmethod
    def chat(
        self,
        model_instance: object,
        messages: list[dict],
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """Chat with the model using message format."""

    @abstractmethod
    def get_model_info(self, model_instance: object) -> dict:
        """Get information about a loaded model."""

    @abstractmethod
    def estimate_memory(self, metadata: ModelMetadata) -> dict:
        """Estimate memory requirements for a model."""

    @abstractmethod
    def get_context_length(self, model_instance: object) -> int:
        """Get the context length of a loaded model."""

    @abstractmethod
    def health_check(self, model_instance: object) -> dict:
        """Run a health check on a loaded model."""


class LocalPyTorchProvider(ModelProvider):
    """PyTorch-based model provider for local models."""

    def __init__(self) -> None:
        self._torch_available = False
        try:
            import torch  # noqa: F401

            self._torch_available = True
        except ImportError:
            logger.info("PyTorch not available")

    def load_model(
        self, metadata: ModelMetadata, device: str = "auto", dtype: str = "auto"
    ) -> object:
        if not self._torch_available:
            raise ModelLoadError(metadata.model_id, "PyTorch is not installed")

        path = Path(metadata.path)
        if not path.exists():
            raise ModelLoadError(metadata.model_id, f"Path does not exist: {path}")

        resolved_device = self._resolve_device(device)
        resolved_dtype = self._resolve_dtype(dtype, resolved_device)
        model = self._load_model_from_path(path, metadata, resolved_device, resolved_dtype)
        if model is None:
            raise ModelLoadError(metadata.model_id, "Could not load model from path")
        return model

    def unload_model(self, model_instance: object) -> None:
        try:
            import torch

            if hasattr(model_instance, "cpu"):
                model_instance.cpu()
            del model_instance
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:
            raise ModelUnloadError("unknown", str(e)) from e

    def is_loaded(self, model_instance: object) -> bool:
        if model_instance is None:
            return False
        if hasattr(model_instance, "parameters"):
            try:
                params = list(model_instance.parameters())
                return len(params) > 0
            except Exception:
                return False
        return False

    def generate(
        self,
        model_instance: object,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> GenerationResult:
        try:
            import torch

            if not self.is_loaded(model_instance):
                return GenerationResult(
                    text="",
                    finish_reason="error",
                    usage={"error": "Model not loaded"},
                )

            tokenizer = self._get_tokenizer_from_model(model_instance)
            if tokenizer is None:
                return GenerationResult(
                    text="",
                    finish_reason="error",
                    usage={"error": "No tokenizer available"},
                )

            input_ids = tokenizer.encode(prompt, return_tensors="pt")
            dev = next(model_instance.parameters()).device  # type: ignore[attr-defined]
            input_ids = input_ids.to(dev)

            with torch.no_grad():
                outputs = model_instance.generate(  # type: ignore[attr-defined]
                    input_ids,
                    max_new_tokens=max_tokens,
                    temperature=max(temperature, 1e-7),
                    top_p=top_p,
                    do_sample=temperature > 0.01,
                    pad_token_id=getattr(tokenizer, "eos_token_id", 0) or 0,
                )

            new_tokens = outputs[0][input_ids.shape[-1] :]
            generated_text = tokenizer.decode(new_tokens, skip_special_tokens=True)

            return GenerationResult(
                text=generated_text,
                tokens=new_tokens.tolist(),
                finish_reason="stop",
                usage={
                    "prompt_tokens": input_ids.shape[-1],
                    "completion_tokens": len(new_tokens),
                    "total_tokens": input_ids.shape[-1] + len(new_tokens),
                },
            )
        except Exception as e:
            logger.debug("Generation failed: %s", e)
            return GenerationResult(
                text="",
                finish_reason="error",
                usage={"error": str(e)},
            )

    def stream_generate(
        self,
        model_instance: object,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> Any:
        result = self.generate(model_instance, prompt, max_tokens, temperature, top_p)
        for char in result.text:
            yield StreamToken(text=char, is_end=False)
        yield StreamToken(text="", is_end=True)

    def chat(
        self,
        model_instance: object,
        messages: list[dict],
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> GenerationResult:
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"{role}: {content}")
        prompt_parts.append("assistant:")
        prompt = "\n".join(prompt_parts)
        return self.generate(model_instance, prompt, max_tokens, temperature)

    def get_model_info(self, model_instance: object) -> dict:
        info: dict = {"loaded": self.is_loaded(model_instance)}
        if model_instance is None:
            return info
        try:
            if hasattr(model_instance, "parameters"):
                params = list(model_instance.parameters())
                total_params = sum(p.numel() for p in params)
                info["parameter_count"] = total_params
                info["parameter_count_str"] = _format_parameter_count(total_params)
                if params:
                    info["dtype"] = str(params[0].dtype).replace("torch.", "")
                    info["device"] = str(params[0].device)
            if hasattr(model_instance, "config"):
                config = model_instance.config
                if hasattr(config, "vocab_size"):
                    info["vocab_size"] = config.vocab_size
                if hasattr(config, "max_position_embeddings"):
                    info["context_length"] = config.max_position_embeddings
                if hasattr(config, "hidden_size"):
                    info["hidden_size"] = config.hidden_size
                if hasattr(config, "num_hidden_layers"):
                    info["num_layers"] = config.num_hidden_layers
        except Exception as e:
            logger.debug("Failed to get model info: %s", e)
        return info

    def estimate_memory(self, metadata: ModelMetadata) -> dict:
        param_count = metadata.parameter_count or 0
        dtype = metadata.dtype if metadata.dtype != "auto" else "float32"
        bytes_per_param = {"float32": 4, "float16": 2, "bfloat16": 2, "int8": 1, "int4": 0.5}
        bp = bytes_per_param.get(dtype, 4)
        model_gb = (param_count * bp) / (1024**3) if param_count > 0 else 0
        overhead_gb = model_gb * 0.1 if model_gb > 0 else 0
        kv_cache_gb = 0.0
        if metadata.context_length and param_count > 0:
            kv_cache_gb = (2 * 32 * metadata.context_length * 4096 * 2) / (1024**3)
        total_gb = model_gb + overhead_gb + kv_cache_gb
        return {
            "model_memory_gb": round(model_gb, 2),
            "overhead_gb": round(overhead_gb, 2),
            "kv_cache_gb": round(kv_cache_gb, 2),
            "total_gb": round(total_gb, 2),
            "dtype": dtype,
            "parameter_count": param_count,
        }

    def get_context_length(self, model_instance: object) -> int:
        if model_instance is None:
            return 0
        try:
            if hasattr(model_instance, "config"):
                config = model_instance.config
                for attr in ("max_position_embeddings", "n_positions", "max_sequence_length"):
                    if hasattr(config, attr):
                        return int(getattr(config, attr))
        except Exception as e:
            logger.debug("Failed to get context length: %s", e)
        return 0

    def health_check(self, model_instance: object) -> dict:
        result: dict = {
            "healthy": False,
            "loaded": self.is_loaded(model_instance),
            "device": "unknown",
            "dtype": "unknown",
        }
        if not result["loaded"]:
            return result
        try:
            params = list(model_instance.parameters())  # type: ignore[attr-defined]
            if params:
                result["device"] = str(params[0].device)
                result["dtype"] = str(params[0].dtype).replace("torch.", "")
                result["healthy"] = True
        except Exception:
            pass
        return result

    def _resolve_device(self, device: str) -> str:
        import torch

        if device == "auto":
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        return device

    def _resolve_dtype(self, dtype: str, device: str) -> str:
        import torch

        if dtype == "auto":
            if device == "cuda" and torch.cuda.is_available():
                if hasattr(torch.cuda, "is_bf16_supported") and torch.cuda.is_bf16_supported():
                    return "bfloat16"
                return "float16"
            return "float32"
        return dtype

    def _load_model_from_path(
        self,
        path: Path,
        metadata: ModelMetadata,  # noqa: ARG002
        device: str,
        dtype: str,
    ) -> Any:
        try:
            hf_files = ["config.json", "pytorch_model.bin", "model.safetensors"]
            has_hf = any((path / f).exists() for f in hf_files)
            if has_hf:
                return self._load_huggingface_model(path, device, dtype)

            pt_files = list(path.glob("*.pt")) + list(path.glob("*.pth"))
            if pt_files:
                return self._load_pytorch_checkpoint(pt_files[0], device, dtype)

            safetensor_files = list(path.glob("*.safetensors"))
            if safetensor_files:
                return self._load_safetensors_model(path, safetensor_files, device, dtype)
        except Exception as e:
            logger.debug("Model loading failed: %s", e)
        return None

    def _load_huggingface_model(self, path: Path, device: str, dtype: str) -> Any:
        try:
            from transformers import AutoConfig, AutoModelForCausalLM

            config = AutoConfig.from_pretrained(str(path), trust_remote_code=True)
            torch_dtype = _str_to_torch_dtype(dtype)
            model = AutoModelForCausalLM.from_pretrained(
                str(path),
                config=config,
                torch_dtype=torch_dtype,
                device_map=device if device != "cpu" else None,
                trust_remote_code=True,
            )
            if device == "cpu":
                model = model.to("cpu")
            model.eval()
            return model
        except Exception as e:
            logger.debug("HuggingFace loading failed: %s", e)
        return None

    def _load_pytorch_checkpoint(
        self,
        file_path: Path,
        device: str,
        dtype: str,  # noqa: ARG002
    ) -> Any:
        try:
            import torch

            state_dict = torch.load(str(file_path), map_location=device, weights_only=True)
            if isinstance(state_dict, dict) and "model" in state_dict:
                return state_dict["model"]
            return state_dict
        except Exception as e:
            logger.debug("PyTorch checkpoint loading failed: %s", e)
        return None

    def _load_safetensors_model(
        self, path: Path, files: list[Path], device: str, dtype: str
    ) -> Any:
        try:
            if (path / "config.json").exists():
                return self._load_huggingface_model(path, device, dtype)
        except Exception:
            pass
        try:
            import torch
            from safetensors.torch import load_file

            torch_dtype = _str_to_torch_dtype(dtype)
            merged: dict = {}
            for f in files:
                merged.update(load_file(str(f)))
            model = torch.nn.Module()
            model.load_state_dict(merged, strict=False)
            model = model.to(device=device, dtype=torch_dtype)
            model.eval()
            return model
        except Exception as e:
            logger.debug("SafeTensors loading failed: %s", e)
        return None

    def _get_tokenizer_from_model(self, model_instance: object) -> Any:
        if hasattr(model_instance, "tokenizer"):
            return model_instance.tokenizer
        return None


def _str_to_torch_dtype(dtype_str: str) -> Any:
    import torch

    dtype_map = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "int8": torch.int8,
    }
    return dtype_map.get(dtype_str, torch.float32)
