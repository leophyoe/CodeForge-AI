"""Model memory estimation for CodeForge AI."""

from __future__ import annotations

from .models import ModelMemoryEstimate

# Bytes per element for each dtype
DTYPE_SIZES = {
    "float32": 4,
    "float16": 2,
    "bfloat16": 2,
    "int8": 1,
    "int4": 0.5,
}


def estimate_model_memory(
    parameter_count: float,
    dtype: str = "float32",
    quantization: str = "none",
    context_length: int = 0,
    kv_cache_ratio: float = 0.5,
) -> ModelMemoryEstimate:
    """Estimate memory requirements for a model.

    This is an ESTIMATE. Actual memory usage depends on many factors
    including framework overhead, batch size, and implementation details.

    Args:
        parameter_count: Number of model parameters (e.g., 7_000_000_000 for 7B).
        dtype: Data type string ("float32", "float16", "bfloat16", "int8", "int4").
        quantization: Quantization method ("none", "int8", "int4", "gptq", "awq").
        context_length: Context length for KV cache estimation.
        kv_cache_ratio: Ratio of KV cache size to model size per token.

    Returns:
        ModelMemoryEstimate with memory estimates (clearly labeled as estimates).
    """
    # Base bytes per parameter
    base_bytes = DTYPE_SIZES.get(dtype, 4)

    # Apply quantization reduction
    quant_factor = _get_quantization_factor(quantization)
    effective_bytes = base_bytes * quant_factor

    # Model memory
    model_memory_bytes = parameter_count * effective_bytes
    model_memory_gb = model_memory_bytes / (1024**3)

    # KV cache estimation
    kv_cache_gb = 0.0
    if context_length > 0:
        # Rough estimate: KV cache scales with context length and model size
        kv_cache_bytes = parameter_count * kv_cache_ratio * base_bytes * (context_length / 4096)
        kv_cache_gb = kv_cache_bytes / (1024**3)

    # Runtime overhead (framework, intermediate tensors, etc.)
    runtime_overhead_gb = model_memory_gb * 0.2  # ~20% overhead estimate

    # Total
    total_gb = model_memory_gb + kv_cache_gb + runtime_overhead_gb

    # Recommendations (with headroom)
    recommended_ram_gb = total_gb * 1.5  # 50% headroom for system
    recommended_vram_gb = total_gb * 1.1  # 10% headroom for GPU

    return ModelMemoryEstimate(
        parameter_count=parameter_count,
        dtype=dtype,
        quantization=quantization,
        context_length=context_length,
        estimated_model_memory_gb=round(model_memory_gb, 2),
        estimated_kv_cache_gb=round(kv_cache_gb, 2),
        estimated_runtime_memory_gb=round(runtime_overhead_gb, 2),
        recommended_ram_gb=round(recommended_ram_gb, 2),
        recommended_vram_gb=round(recommended_vram_gb, 2),
        is_estimate=True,
    )


def _get_quantization_factor(quantization: str) -> float:
    """Get the memory reduction factor for quantization."""
    factors = {
        "none": 1.0,
        "int8": 0.5,
        "int4": 0.25,
        "gptq": 0.25,
        "awq": 0.25,
        "gguf": 0.25,
    }
    return factors.get(quantization.lower(), 1.0)
