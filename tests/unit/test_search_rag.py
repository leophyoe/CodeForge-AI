import math

from codeforge.packages.chunks.chunker import CodeChunker
from codeforge.packages.chunks.models import CodeChunk
from codeforge.packages.embeddings.cache import EmbeddingCache
from codeforge.packages.embeddings.manager import EmbeddingManager
from codeforge.packages.embeddings.models import (
    Embedding,
    EmbeddingConfig,
    EmbeddingResult,
    content_hash,
)
from codeforge.packages.embeddings.provider import FallbackEmbeddingProvider
from codeforge.packages.rag.context import ContextBuilder
from codeforge.packages.rag.models import RAGConfig, RAGQuery, RAGResponse, SourceReference
from codeforge.packages.rag.retriever import RAGRetriever
from codeforge.packages.rag.service import RAGService
from codeforge.packages.search.hybrid import HybridSearch
from codeforge.packages.search.lexical import LexicalSearch
from codeforge.packages.search.models import SearchMode, SearchQuery
from codeforge.packages.search.symbol import SymbolSearch
from codeforge.packages.vector.memory import InMemoryVectorStore
from codeforge.packages.vector.models import VectorRecord


class TestEmbeddingModels:
    def test_embedding_creation(self):
        e = Embedding(vector=[0.1, 0.2, 0.3])
        assert e.dimension == 3

    def test_embedding_normalization(self):
        e = Embedding(vector=[3.0, 4.0])
        e.normalize_vector()
        norm = math.sqrt(sum(x * x for x in e.vector))
        assert abs(norm - 1.0) < 1e-6

    def test_embedding_config(self):
        config = EmbeddingConfig(dimension=128)
        assert config.dimension == 128
        assert config.normalize is True

    def test_embedding_result(self):
        r = EmbeddingResult(text="hello", model="test")
        assert r.text == "hello"

    def test_content_hash(self):
        h = content_hash("test")
        assert len(h) == 64
        assert h == content_hash("test")
        assert h != content_hash("other")


class TestFallbackProvider:
    def test_embed_text(self):
        provider = FallbackEmbeddingProvider(dimension=128)
        e = provider.embed_text("hello world")
        assert e.dimension == 128
        assert len(e.vector) == 128

    def test_embed_batch(self):
        provider = FallbackEmbeddingProvider(dimension=64)
        results = provider.embed_batch(["a", "b", "c"])
        assert len(results) == 3
        assert all(r.dimension == 64 for r in results)

    def test_deterministic(self):
        provider = FallbackEmbeddingProvider(dimension=32)
        e1 = provider.embed_text("same text")
        e2 = provider.embed_text("same text")
        assert e1.vector == e2.vector

    def test_different_texts_different_embeddings(self):
        provider = FallbackEmbeddingProvider(dimension=32)
        e1 = provider.embed_text("text one")
        e2 = provider.embed_text("text two")
        assert e1.vector != e2.vector

    def test_health_check(self):
        provider = FallbackEmbeddingProvider()
        assert provider.health_check() is True

    def test_get_dimension(self):
        provider = FallbackEmbeddingProvider(dimension=256)
        assert provider.get_dimension() == 256


class TestEmbeddingCache:
    def test_put_get(self, tmp_path):
        cache = EmbeddingCache(str(tmp_path / "cache.db"))
        e = Embedding(vector=[0.1, 0.2], dimension=2)
        cache.put("hello", "model1", e)
        result = cache.get("hello", "model1")
        assert result is not None
        assert result.vector == [0.1, 0.2]

    def test_cache_miss(self, tmp_path):
        cache = EmbeddingCache(str(tmp_path / "cache.db"))
        result = cache.get("missing", "model1")
        assert result is None

    def test_invalidate(self, tmp_path):
        cache = EmbeddingCache(str(tmp_path / "cache.db"))
        e = Embedding(vector=[0.1], dimension=1)
        cache.put("hello", "model1", e)
        assert cache.invalidate("hello", "model1") is True
        assert cache.get("hello", "model1") is None

    def test_count(self, tmp_path):
        cache = EmbeddingCache(str(tmp_path / "cache.db"))
        e = Embedding(vector=[0.1], dimension=1)
        cache.put("a", "m", e)
        cache.put("b", "m", e)
        assert cache.count() == 2

    def test_clear(self, tmp_path):
        cache = EmbeddingCache(str(tmp_path / "cache.db"))
        e = Embedding(vector=[0.1], dimension=1)
        cache.put("a", "m", e)
        assert cache.clear() == 1
        assert cache.count() == 0


class TestEmbeddingManager:
    def test_embed(self, tmp_path):
        manager = EmbeddingManager(
            config=EmbeddingConfig(dimension=64),
            cache=EmbeddingCache(str(tmp_path / "cache.db")),
        )
        result = manager.embed("hello world")
        assert result.embedding is not None
        assert result.embedding.dimension == 64
        assert result.cached is False

    def test_embed_cache_hit(self, tmp_path):
        manager = EmbeddingManager(
            config=EmbeddingConfig(dimension=64),
            cache=EmbeddingCache(str(tmp_path / "cache.db")),
        )
        r1 = manager.embed("hello")
        r2 = manager.embed("hello")
        assert r2.cached is True
        assert r1.embedding.vector == r2.embedding.vector

    def test_embed_batch(self, tmp_path):
        manager = EmbeddingManager(
            config=EmbeddingConfig(dimension=32),
            cache=EmbeddingCache(str(tmp_path / "cache.db")),
        )
        results = manager.embed_batch(["a", "b", "c"])
        assert len(results) == 3

    def test_health_check(self, tmp_path):
        manager = EmbeddingManager(
            cache=EmbeddingCache(str(tmp_path / "cache.db")),
        )
        assert manager.health_check() is True


class TestCodeChunk:
    def test_chunk_creation(self):
        chunk = CodeChunk(content="def hello(): pass", language="python")
        assert chunk.content_hash != ""
        assert chunk.token_estimate() > 0

    def test_chunk_to_dict(self):
        chunk = CodeChunk(
            content="test",
            relative_path="test.py",
            symbol_name="hello",
        )
        d = chunk.to_dict()
        assert d["relative_path"] == "test.py"
        assert d["symbol_name"] == "hello"


class TestCodeChunker:
    def test_chunk_python(self):
        source = "class User:\n    def save(self):\n        pass\n"
        chunker = CodeChunker()
        chunks = chunker.chunk_file(source, "python")
        assert len(chunks) > 0
        assert any(c.symbol_name for c in chunks)

    def test_chunk_javascript(self):
        source = "function hello() {\n    return 1;\n}\n"
        chunker = CodeChunker()
        chunks = chunker.chunk_file(source, "javascript")
        assert len(chunks) > 0

    def test_chunk_empty(self):
        chunker = CodeChunker()
        chunks = chunker.chunk_file("", "python")
        assert len(chunks) == 0

    def test_chunk_with_symbols(self):
        source = "class User:\n    def save(self):\n        pass\n"
        symbols = [
            {
                "name": "User",
                "kind": "class",
                "start_line": 0,
                "end_line": 2,
                "qualified_name": "User",
            },
            {
                "name": "save",
                "kind": "method",
                "start_line": 1,
                "end_line": 2,
                "qualified_name": "User.save",
            },
        ]
        chunker = CodeChunker()
        chunks = chunker.chunk_file(source, "python", symbols=symbols)
        assert len(chunks) >= 1


class TestInMemoryVectorStore:
    def test_add_and_search(self):
        store = InMemoryVectorStore()
        record = VectorRecord(
            chunk_id="c1",
            workspace_id="ws1",
            embedding=[1.0, 0.0, 0.0],
            metadata={"content": "hello"},
        )
        store.add(record)
        results = store.search([1.0, 0.0, 0.0], "ws1", top_k=1)
        assert len(results) == 1
        assert results[0].score > 0.9

    def test_upsert(self):
        store = InMemoryVectorStore()
        r1 = VectorRecord(chunk_id="c1", workspace_id="ws1", embedding=[1.0, 0.0])
        r2 = VectorRecord(chunk_id="c1", workspace_id="ws1", embedding=[0.0, 1.0])
        store.add(r1)
        store.upsert(r2)
        assert store.count("ws1") == 1

    def test_delete(self):
        store = InMemoryVectorStore()
        r = VectorRecord(chunk_id="c1", workspace_id="ws1", embedding=[1.0])
        store.add(r)
        assert store.delete(r.id) is True
        assert store.count("ws1") == 0

    def test_delete_by_workspace(self):
        store = InMemoryVectorStore()
        store.add(VectorRecord(chunk_id="c1", workspace_id="ws1", embedding=[1.0]))
        store.add(VectorRecord(chunk_id="c2", workspace_id="ws2", embedding=[1.0]))
        deleted = store.delete_by_workspace("ws1")
        assert deleted == 1
        assert store.count("ws1") == 0
        assert store.count("ws2") == 1

    def test_workspace_isolation(self):
        store = InMemoryVectorStore()
        store.add(VectorRecord(chunk_id="c1", workspace_id="ws1", embedding=[1.0, 0.0]))
        store.add(VectorRecord(chunk_id="c2", workspace_id="ws2", embedding=[1.0, 0.0]))
        results = store.search([1.0, 0.0], "ws1")
        assert len(results) == 1
        assert results[0].chunk_id == "c1"

    def test_count(self):
        store = InMemoryVectorStore()
        store.add(VectorRecord(chunk_id="c1", workspace_id="ws1", embedding=[1.0]))
        store.add(VectorRecord(chunk_id="c2", workspace_id="ws2", embedding=[1.0]))
        assert store.count() == 2
        assert store.count("ws1") == 1

    def test_health_check(self):
        store = InMemoryVectorStore()
        assert store.health_check() is True


class TestLexicalSearch:
    def test_exact_match(self):
        search = LexicalSearch()
        query = SearchQuery(query="UserService", limit=10)
        chunks = [
            {"chunk_id": "c1", "content": "class UserService:", "language": "python"},
            {"chunk_id": "c2", "content": "class ProductService:", "language": "python"},
        ]
        results = search.search(query, chunks)
        assert len(results) == 1
        assert "UserService" in results[0].content

    def test_case_insensitive(self):
        search = LexicalSearch()
        query = SearchQuery(query="userservice", case_sensitive=False)
        chunks = [{"chunk_id": "c1", "content": "class UserService:"}]
        results = search.search(query, chunks)
        assert len(results) == 1

    def test_language_filter(self):
        search = LexicalSearch()
        query = SearchQuery(query="def", language="python")
        chunks = [
            {"chunk_id": "c1", "content": "def hello():", "language": "python"},
            {"chunk_id": "c2", "content": "function hello()", "language": "javascript"},
        ]
        results = search.search(query, chunks)
        assert len(results) == 1
        assert results[0].language == "python"

    def test_regex_mode(self):
        search = LexicalSearch()
        query = SearchQuery(query=r"def \w+\(", use_regex=True)
        chunks = [
            {"chunk_id": "c1", "content": "def hello():", "language": "python"},
            {"chunk_id": "c2", "content": "class hello:", "language": "python"},
        ]
        results = search.search(query, chunks)
        # Old code ran re.escape() even in regex mode, so \w+ never matched.
        assert len(results) == 1
        assert results[0].chunk_id == "c1"

    def test_regex_invalid_pattern_falls_back_to_literal(self):
        search = LexicalSearch()
        query = SearchQuery(query="def foo(", use_regex=True)
        chunks = [{"chunk_id": "c1", "content": "syntax error near def foo("}]
        results = search.search(query, chunks)
        assert len(results) == 1
        assert results[0].chunk_id == "c1"


class TestSymbolSearch:
    def test_exact_symbol(self):
        search = SymbolSearch()
        query = SearchQuery(query="UserService", limit=10)
        symbols = [
            {
                "name": "UserService",
                "qualified_name": "UserService",
                "kind": "class",
                "file_id": "f1",
            },
        ]
        results = search.search(query, symbols)
        assert len(results) == 1
        assert results[0].score >= 0.9

    def test_partial_match(self):
        search = SymbolSearch()
        query = SearchQuery(query="User", limit=10)
        symbols = [
            {
                "name": "UserService",
                "qualified_name": "UserService",
                "kind": "class",
                "file_id": "f1",
            },
        ]
        results = search.search(query, symbols)
        assert len(results) == 1
        assert results[0].score > 0


class TestHybridSearch:
    def test_hybrid_results(self):
        hybrid = HybridSearch()
        query = SearchQuery(query="UserService", limit=10)
        chunks = [
            {"chunk_id": "c1", "content": "class UserService:", "language": "python"},
        ]
        symbols = [
            {
                "name": "UserService",
                "qualified_name": "UserService",
                "kind": "class",
                "file_id": "f1",
            },
        ]
        results = hybrid.search(query, chunks=chunks, symbols=symbols)
        assert len(results) >= 1

    def test_lexical_only(self):
        hybrid = HybridSearch()
        query = SearchQuery(query="test", mode=SearchMode.LEXICAL)
        chunks = [{"chunk_id": "c1", "content": "test function"}]
        results = hybrid.search(query, chunks=chunks)
        assert len(results) >= 1


class TestContextBuilder:
    def test_build_context(self):
        builder = ContextBuilder(RAGConfig(max_context_tokens=1000))
        results = [
            {
                "chunk_id": "c1",
                "relative_path": "src/auth.py",
                "start_line": 10,
                "end_line": 20,
                "symbol_name": "authenticate",
                "content": "def authenticate(): pass",
            }
        ]
        context, sources = builder.build_context(results)
        assert "src/auth.py" in context
        assert len(sources) == 1
        assert sources[0].file_path == "src/auth.py"

    def test_token_budget(self):
        builder = ContextBuilder(RAGConfig(max_context_tokens=50))
        results = [
            {
                "chunk_id": f"c{i}",
                "relative_path": f"f{i}.py",
                "start_line": 0,
                "end_line": 10,
                "content": "x" * 200,
            }
            for i in range(10)
        ]
        context, sources = builder.build_context(results)
        tokens = builder.estimate_tokens(context)
        assert tokens <= 100

    def test_build_prompt(self):
        builder = ContextBuilder()
        messages = builder.build_prompt("How does auth work?", "context here")
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[2]["role"] == "user"


class TestRAGRetriever:
    def test_retrieve(self):
        hybrid = HybridSearch()
        retriever = RAGRetriever(hybrid)
        query = RAGQuery(workspace_id="ws1", query="test", top_k=5)
        chunks = [{"chunk_id": "c1", "content": "test code"}]
        results = retriever.retrieve(query, chunks=chunks)
        assert isinstance(results, list)


class TestRAGService:
    def test_query(self):
        hybrid = HybridSearch()
        service = RAGService(hybrid)
        query = RAGQuery(workspace_id="ws1", query="test", top_k=5)
        chunks = [{"chunk_id": "c1", "content": "test code"}]
        service.update_context(chunks, [])
        response = service.query(query)
        assert isinstance(response, RAGResponse)
        assert response.answer != ""


class TestSourceReference:
    def test_format(self):
        ref = SourceReference(
            file_path="src/auth.py",
            start_line=10,
            end_line=20,
            symbol="authenticate",
        )
        formatted = ref.format()
        assert "src/auth.py" in formatted
        assert "10-20" in formatted
        assert "authenticate" in formatted


class TestRAGConfig:
    def test_defaults(self):
        config = RAGConfig()
        assert config.enabled is True
        assert config.top_k == 8
        assert config.max_context_tokens == 4000

    def test_to_dict(self):
        config = RAGConfig()
        d = config.to_dict()
        assert "enabled" in d
        assert "top_k" in d
