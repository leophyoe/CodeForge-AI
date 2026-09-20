"""Tests for ModelCache."""

from codeforge.packages.models.cache import ModelCache


class TestModelCache:
    def test_add_and_get(self) -> None:
        cache = ModelCache()
        cache.add("m1", "model_instance")
        assert cache.get("m1") == "model_instance"

    def test_get_missing(self) -> None:
        cache = ModelCache()
        assert cache.get("nonexistent") is None

    def test_contains(self) -> None:
        cache = ModelCache()
        cache.add("m1", "inst")
        assert cache.contains("m1") is True
        assert cache.contains("m2") is False

    def test_remove(self) -> None:
        cache = ModelCache()
        cache.add("m1", "inst")
        assert cache.remove("m1") is True
        assert cache.get("m1") is None
        assert cache.remove("m1") is False

    def test_list_loaded(self) -> None:
        cache = ModelCache()
        cache.add("m1", "inst1")
        cache.add("m2", "inst2")
        loaded = cache.list_loaded()
        assert "m1" in loaded
        assert "m2" in loaded

    def test_size(self) -> None:
        cache = ModelCache()
        assert cache.size() == 0
        cache.add("m1", "inst")
        assert cache.size() == 1

    def test_clear(self) -> None:
        cache = ModelCache()
        cache.add("m1", "inst1")
        cache.add("m2", "inst2")
        cache.clear()
        assert cache.size() == 0

    def test_replace_existing(self) -> None:
        cache = ModelCache()
        cache.add("m1", "old")
        cache.add("m1", "new")
        assert cache.get("m1") == "new"
