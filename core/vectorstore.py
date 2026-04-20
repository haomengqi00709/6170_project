"""
RBAC-Filtered Vector Store
---------------------------
Wraps Chroma with pre-retrieval permission filtering.

Document metadata schema:
    content_level   str   — one of PERMISSION_LEVELS
    department      str   — owning department (optional filter)
    source          str   — original filename

Key property: the Chroma `where` filter is applied BEFORE the ANN search,
so the LLM never sees content above the user's clearance level.
"""

import os
from pathlib import Path
from typing import List

import chromadb

from core.rbac import User, levels_at_or_below, PERMISSION_LEVELS
from core import llm as _llm

COLLECTION_NAME = "auditbot"
CHUNK_SIZE      = 800
CHUNK_OVERLAP   = 100


class AuditBotVectorStore:
    def __init__(self, db_dir: str = "chroma_db"):
        self._client = chromadb.PersistentClient(path=db_dir)
        self._col = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=_llm.get_chroma_embedding_fn(),
        )

    # ── Ingest ────────────────────────────────────────────────────────────────
    def ingest_chunk(
        self,
        text: str,
        chunk_id: str,
        content_level: str,
        source: str,
        department: str = "general",
    ) -> None:
        """Add a single chunk with permission metadata."""
        if content_level not in PERMISSION_LEVELS:
            raise ValueError(f"Invalid content_level '{content_level}'")
        self._col.upsert(
            documents=[text],
            ids=[chunk_id],
            metadatas=[{
                "content_level": content_level,
                "department": department,
                "source": source,
            }],
        )

    def ingest_file(
        self,
        filepath: str | Path,
        content_level: str,
        department: str = "general",
    ) -> int:
        """Chunk a text file and ingest all chunks. Returns chunk count."""
        path = Path(filepath)
        text = path.read_text(encoding="utf-8", errors="ignore")
        chunks = _chunk(text)
        for i, chunk in enumerate(chunks):
            self.ingest_chunk(
                text=chunk,
                chunk_id=f"{path.name}__chunk_{i}",
                content_level=content_level,
                source=path.name,
                department=department,
            )
        return len(chunks)

    # ── Query ─────────────────────────────────────────────────────────────────
    def query(self, question: str, user: User, k: int = 5) -> List[dict]:
        """
        Retrieve top-k chunks the user is permitted to see.
        The permission filter is applied at the Chroma level (pre-retrieval).
        """
        if self._col.count() == 0:
            return []

        allowed = levels_at_or_below(user.level)
        results = self._col.query(
            query_texts=[question],
            n_results=min(k, self._col.count()),
            where={"content_level": {"$in": allowed}},
        )

        docs = []
        for text, meta in zip(results["documents"][0], results["metadatas"][0]):
            docs.append({
                "text":          text,
                "source":        meta.get("source", "unknown"),
                "content_level": meta.get("content_level", "unknown"),
                "department":    meta.get("department", "general"),
            })
        return docs

    def count(self) -> int:
        return self._col.count()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _chunk(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start: start + size])
        start += size - overlap
    return chunks
