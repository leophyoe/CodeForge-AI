"""Tests for precision and model memory estimation."""

from __future__ import annotations

from codeforge.packages.runtime.model_estimator import estimate_model_memory
from codeforge.packages.runtime.models import DeviceType, ModelMemoryEstimate, PrecisionInfo
from codeforge.packages.runtime.precision import PrecisionManager


class TestPrecisionManager:
    def test_get_supported_dtypes_cpu(self) -> None:
        pm = PrecisionManager()
        info = pm.get_supported_dtypes(DeviceType.CPU)
        assert isinstance(info, PrecisionInfo)
        assert info.float32_supported is True

    def test_get_supported_dtypes_cuda(self) -> None:
        pm = PrecisionManager()
        info = pm.get_supported_dtypes(DeviceType.CUDA)
        assert isinstance(info, PrecisionInfo)
        assert info.float32_supported is True

    def test_get_supported_dtypes_mps(self) -> None:
        pm = PrecisionManager()
        info = pm.get_supported_dtypes(DeviceType.MPS)
        assert isinstance(info, PrecisionInfo)
        assert info.float32_supported is True

    def test_select_dtype_auto(self) -> None:
        pm = PrecisionManager()
        dtype = pm.select_dtype(DeviceType.CPU, preferred="auto")
        assert dtype in ("float32", "float16", "bfloat16")

    def test_select_dtype_preferred(self) -> None:
        pm = PrecisionManager()
        dtype = pm.select_dtype(DeviceType.CPU, preferred="float32")
        assert dtype == "float32"

    def test_validate_dtype(self) -> None:
        pm = PrecisionManager()
        assert pm.validate_dtype("float32", DeviceType.CPU) is True

    def test_validate_invalid_dtype(self) -> None:
        pm = PrecisionManager()
        assert pm.validate_dtype("invalid", DeviceType.CPU) is False


class TestModelMemoryEstimator:
    def test_basic_estimate(self) -> None:
        est = estimate_model_memory(
            parameter_count=7_000_000_000,
            dtype="float32",
        )
        assert isinstance(est, ModelMemoryEstimate)
        assert est.is_estimate is True
        assert est.parameter_count == 7_000_000_000
        assert est.estimated_model_memory_gb > 0
        assert est.recommended_ram_gb > 0

    def test_float16_estimate(self) -> None:
        est32 = estimate_model_memory(1_000_000_000, dtype="float32")
        est16 = estimate_model_memory(1_000_000_000, dtype="float16")
        assert est16.estimated_model_memory_gb < est32.estimated_model_memory_gb

    def test_quantization_reduces_memory(self) -> None:
        est_none = estimate_model_memory(1_000_000_000, quantization="none")
        est_int4 = estimate_model_memory(1_000_000_000, quantization="int4")
        assert est_int4.estimated_model_memory_gb < est_none.estimated_model_memory_gb

    def test_kv_cache(self) -> None:
        est = estimate_model_memory(1_000_000_000, context_length=4096)
        assert est.estimated_kv_cache_gb > 0

    def test_small_model(self) -> None:
        est = estimate_model_memory(125_000_000)
        assert est.estimated_model_memory_gb < 1.0
