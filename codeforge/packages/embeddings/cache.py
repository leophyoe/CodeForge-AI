from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Embedding, content_hash


class EmbeddingCache:
    def __init__(self, db_path: str | Path = "embedding_cache.db") -> None:
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embedding_cache (
                cache_key TEXT PRIMARY KEY,
                text_hash TEXT NOT NULL,
                model_id TEXT NOT NULL,
                embedding TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_hash ON embedding_cache(text_hash)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_model ON embedding_cache(model_id)"
        )
        conn.commit()

    def _make_key(self, text: str, model_id: str) -> str:
        import hashlib

        h = hashlib.sha256()
        h.update(text.encode("utf-8"))
        h.update(model_id.encode("utf-8"))
        return h.hexdigest()

    def get(self, text: str, model_id: str) -> Embedding | None:
        key = self._make_key(text, model_id)
        conn = self._get_conn()
        row = conn.execute(
            "SELECT embedding, dimension FROM embedding_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if row:
            vector = json.loads(row["embedding"])
            return Embedding(vector=vector, dimension=row["dimension"])
        return None

    def put(self, text: str, model_id: str, embedding: Embedding) -> None:
        key = self._make_key(text, model_id)
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO embedding_cache
               (cache_key, text_hash, model_id, embedding, dimension, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                key,
                content_hash(text),
                model_id,
                json.dumps(embedding.vector),
                embedding.dimension,
                __import__("time").time(),
            ),
        )
        conn.commit()

    def invalidate(self, text: str, model_id: str) -> bool:
        key = self._make_key(text, model_id)
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM embedding_cache WHERE cache_key = ?", (key,)
        )
        conn.commit()
        return cursor.rowcount > 0

    def invalidate_prefix(self, prefix: str) -> int:
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM embedding_cache WHERE cache_key LIKE ?",
            (f"{prefix}%",),
        )
        conn.commit()
        return cursor.rowcount

    def count(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM embedding_cache").fetchone()
        return row[0] if row else 0

    def clear(self) -> int:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM embedding_cache")
        conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
