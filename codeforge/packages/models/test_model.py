"""Tiny test model for Phase 3 testing.

Creates a minimal transformer model for testing without requiring large LLMs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def create_test_model(output_dir: str | Path) -> Path:
    """Create a tiny test model at the given directory."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        import torch
        import torch.nn as nn  # noqa: F401

        model = TinyTransformer(
            vocab_size=256,
            hidden_size=32,
            num_layers=2,
            num_heads=2,
            max_seq_len=128,
        )

        config = {
            "architectures": ["TinyTransformerForCausalLM"],
            "model_type": "tiny_transformer",
            "vocab_size": 256,
            "hidden_size": 32,
            "num_hidden_layers": 2,
            "num_attention_heads": 2,
            "intermediate_size": 64,
            "max_position_embeddings": 128,
        }

        with open(output_path / "config.json", "w") as f:
            json.dump(config, f, indent=2)

        state_dict = model.state_dict()
        torch.save(state_dict, output_path / "pytorch_model.bin")

        _create_test_tokenizer(output_path)

        logger.info("Created test model at %s", output_path)
        return output_path

    except ImportError:
        logger.warning("PyTorch not available, creating minimal test model files")
        config = {
            "architectures": ["TinyTransformerForCausalLM"],
            "model_type": "tiny_transformer",
            "vocab_size": 256,
            "hidden_size": 32,
            "num_hidden_layers": 2,
            "num_attention_heads": 2,
            "intermediate_size": 64,
            "max_position_embeddings": 128,
        }
        with open(output_path / "config.json", "w") as f:
            json.dump(config, f, indent=2)
        _create_test_tokenizer(output_path)
        return output_path


def _create_test_tokenizer(output_path: Path) -> None:
    """Create a minimal test tokenizer."""
    vocab: dict[str, int] = {}
    for i in range(256):
        vocab[f"token_{i}"] = i

    tokenizer_config = {
        "model_max_length": 128,
        "bos_token": {"content": "token_0", "lstrip": False, "rstrip": False},
        "eos_token": {"content": "token_1", "lstrip": False, "rstrip": False},
    }

    with open(output_path / "tokenizer_config.json", "w") as f:
        json.dump(tokenizer_config, f, indent=2)

    special_tokens_map = {
        "bos_token": "token_0",
        "eos_token": "token_1",
    }
    with open(output_path / "special_tokens_map.json", "w") as f:
        json.dump(special_tokens_map, f, indent=2)


class TinyTransformer:
    """Minimal transformer for testing."""

    def __init__(
        self,
        vocab_size: int = 256,
        hidden_size: int = 32,
        num_layers: int = 2,
        num_heads: int = 2,
        max_seq_len: int = 128,
    ) -> None:
        import torch.nn as nn

        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.max_seq_len = max_seq_len

        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.position_embedding = nn.Embedding(max_seq_len, hidden_size)

        self.layers = nn.ModuleList()
        for _ in range(num_layers):
            self.layers.append(TransformerBlock(hidden_size, num_heads))

        self.lm_head = nn.Linear(hidden_size, vocab_size, bias=False)
        self.lm_head.weight = self.embedding.weight

    def state_dict(self) -> dict[str, Any]:
        """Get state dict from all submodules."""

        state: dict[str, Any] = {}
        modules = {
            "embedding": self.embedding,
            "position_embedding": self.position_embedding,
            "lm_head": self.lm_head,
        }
        for name, mod in modules.items():
            for k, v in mod.state_dict().items():
                state[f"{name}.{k}"] = v
        for i, layer in enumerate(self.layers):
            for k, v in layer.state_dict().items():
                state[f"layers.{i}.{k}"] = v
        return state

    def forward(self, input_ids: Any) -> Any:
        import torch

        seq_len = input_ids.shape[-1]
        positions = torch.arange(0, seq_len, device=input_ids.device).unsqueeze(0)

        x = self.embedding(input_ids) + self.position_embedding(positions)

        for layer in self.layers:
            x = layer(x)

        return self.lm_head(x)

    def generate(self, input_ids: Any, max_new_tokens: int = 10, **kwargs: Any) -> Any:  # noqa: ARG002
        import torch

        for _ in range(max_new_tokens):
            logits = self.forward(input_ids)
            next_token_logits = logits[:, -1, :]
            next_token = torch.argmax(next_token_logits, dim=-1, keepdim=True)
            input_ids = torch.cat([input_ids, next_token], dim=-1)
            if input_ids.shape[-1] >= self.max_seq_len:
                break
        return input_ids

    def parameters(self) -> Any:
        all_params = list(self.embedding.parameters())
        all_params += list(self.position_embedding.parameters())
        for layer in self.layers:
            all_params += list(layer.parameters())
        all_params += list(self.lm_head.parameters())
        return iter(all_params)

    def eval(self) -> TinyTransformer:
        return self

    def cpu(self) -> TinyTransformer:
        return self

    @property
    def config(self) -> TinyConfig:
        return TinyConfig(
            vocab_size=self.vocab_size,
            hidden_size=self.hidden_size,
            num_hidden_layers=self.num_layers,
            max_position_embeddings=self.max_seq_len,
        )


class TinyConfig:
    """Minimal config for testing."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class TransformerBlock:
    """Minimal transformer block."""

    def __init__(self, hidden_size: int, num_heads: int) -> None:
        import torch.nn as nn
        self.attention = nn.MultiheadAttention(hidden_size, num_heads, batch_first=True)
        self.norm1 = nn.LayerNorm(hidden_size)
        self.norm2 = nn.LayerNorm(hidden_size)
        self.ff = nn.Sequential(
            nn.Linear(hidden_size, hidden_size * 2),
            nn.GELU(),
            nn.Linear(hidden_size * 2, hidden_size),
        )

    def forward(self, x: Any) -> Any:
        attn_out, _ = self.attention(x, x, x)
        x = self.norm1(x + attn_out)
        ff_out = self.ff(x)
        return self.norm2(x + ff_out)

    def state_dict(self) -> dict[str, Any]:
        """Get state dict."""
        state: dict[str, Any] = {}
        for name, mod in [("attention", self.attention), ("norm1", self.norm1),
                          ("norm2", self.norm2), ("ff", self.ff)]:
            for k, v in mod.state_dict().items():
                state[f"{name}.{k}"] = v
        return state
