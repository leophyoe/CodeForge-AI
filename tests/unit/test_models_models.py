"""Tests for model data models."""

from codeforge.packages.models.models import (
    GenerationResult,
    ModelConfig,
    ModelFormat,
    ModelInspection,
    ModelMetadata,
    ModelStatus,
    ModelTask,
    SafetensorsInfo,
    StreamToken,
    TensorInfo,
)


class TestModelMetadata:
    def test_default_metadata(self) -> None:
        m = ModelMetadata()
        assert m.model_id == ""
        assert m.provider == "pytorch"
        assert m.task == ModelTask.UNKNOWN
        assert m.format == ModelFormat.UNKNOWN

    def test_custom_metadata(self) -> None:
        m = ModelMetadata(
            model_id="test-model",
            name="Test Model",
            path="/models/test",
            task=ModelTask.CAUSAL_LM,
            architecture="GPT2",
            parameter_count=1e9,
            context_length=2048,
        )
        assert m.model_id == "test-model"
        assert m.parameter_count == 1e9
        assert m.context_length == 2048

    def test_metadata_has_timestamps(self) -> None:
        m = ModelMetadata()
        assert m.created_at != ""
        assert m.updated_at != ""


class TestModelConfig:
    def test_default_config(self) -> None:
        c = ModelConfig()
        assert c.provider == "pytorch"
        assert c.dtype == "auto"
        assert c.device == "auto"

    def test_custom_config(self) -> None:
        c = ModelConfig(id="m1", path="/models/m1", dtype="float16")
        assert c.id == "m1"
        assert c.dtype == "float16"


class TestModelInspection:
    def test_inspection_to_dict(self) -> None:
        ins = ModelInspection(
            model_id="test",
            name="Test",
            task="causal-lm",
            status="discovered",
        )
        d = ins.to_dict()
        assert d["model_id"] == "test"
        assert d["task"] == "causal-lm"
        assert "weight_files" in d


class TestEnums:
    def test_model_status_values(self) -> None:
        assert ModelStatus.DISCOVERED.value == "discovered"
        assert ModelStatus.LOADED.value == "loaded"
        assert ModelStatus.FAILED.value == "failed"

    def test_model_format_values(self) -> None:
        assert ModelFormat.SAFETENSORS.value == "safetensors"
        assert ModelFormat.HUGGINGFACE.value == "huggingface"

    def test_model_task_values(self) -> None:
        assert ModelTask.CAUSAL_LM.value == "causal-lm"
        assert ModelTask.EMBEDDING.value == "embedding"


class TestTensorInfo:
    def test_tensor_info(self) -> None:
        t = TensorInfo(name="layer.weight", dtype="float32", shape=[4096, 4096])
        assert t.name == "layer.weight"
        assert len(t.shape) == 2


class TestSafetensorsInfo:
    def test_default_info(self) -> None:
        s = SafetensorsInfo()
        assert s.tensor_count == 0
        assert s.total_size_bytes == 0


class TestGenerationResult:
    def test_generation_result(self) -> None:
        r = GenerationResult(text="hello", tokens=[1, 2, 3], finish_reason="stop")
        assert r.text == "hello"
        assert len(r.tokens) == 3


class TestStreamToken:
    def test_stream_token(self) -> None:
        t = StreamToken(text="a", token_id=1, is_end=False)
        assert t.text == "a"
        assert t.is_end is False
