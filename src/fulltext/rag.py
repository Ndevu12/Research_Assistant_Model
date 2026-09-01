# -*- coding: utf-8 -*-
"""Session-scoped retrieval over full-text chunks.

Chunks are embedded through the existing embedding provider (reusing its
disk cache) and searched by cosine similarity. When the embedding backend
is unavailable, retrieval falls back to BM25 over the chunk texts, so
grounding works in every environment.
"""

from __future__ import annotations

import numpy as np

from ..embeddings.base import EmbeddingProvider, cosine_similarity
from ..research.bm25 import normalized_bm25_scores
from .base import FullTextChunk, RAGIndex


class InMemoryFulltextIndex(RAGIndex):
    """In-memory chunk index for one pipeline run."""

    def __init__(self, embedder: EmbeddingProvider | None = None) -> None:
        self.embedder = embedder
        self._chunks: list[FullTextChunk] = []
        self._vectors: np.ndarray | None = None

    async def index_chunks(self, chunks: list[FullTextChunk]) -> int:
        self._chunks.extend(chunks)
        self._vectors = None  # rebuilt lazily on next search
        return len(chunks)

    def _ensure_vectors(self) -> None:
        if self.embedder is None or self._vectors is not None or not self._chunks:
            return
        try:
            self._vectors = np.asarray(
                self.embedder.embed_texts([chunk.text for chunk in self._chunks])
            )
        except Exception:
            # Embedding backend unavailable at runtime; BM25 fallback takes over.
            self.embedder = None
            self._vectors = None

    def _rank(self, query: str, indices: list[int]) -> list[tuple[int, float]]:
        """Score the given chunk indices against the query, best first."""
        self._ensure_vectors()

        if self._vectors is not None and self.embedder is not None:
            try:
                query_vector = self.embedder.embed_texts([query])[0]
            except Exception:
                self.embedder = None
                return self._rank(query, indices)
            scored = [
                (index, cosine_similarity(query_vector, self._vectors[index]))
                for index in indices
            ]
        else:
            scores = normalized_bm25_scores(
                query, [self._chunks[index].text for index in indices]
            )
            scored = list(zip(indices, scores, strict=True))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        paper_id: str | None = None,
    ) -> list[FullTextChunk]:
        """Return the most relevant chunks, optionally scoped to one paper."""
        if not self._chunks:
            return []

        indices = [
            index
            for index, chunk in enumerate(self._chunks)
            if paper_id is None or chunk.paper_id == paper_id
        ]
        if not indices:
            return []

        ranked = self._rank(query, indices)
        return [self._chunks[index] for index, _ in ranked[:top_k]]
