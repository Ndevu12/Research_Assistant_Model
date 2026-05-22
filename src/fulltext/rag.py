# -*- coding: utf-8 -*-
"""RAG index stubs for future full-text grounded retrieval."""

from __future__ import annotations

from .base import FullTextChunk, RAGIndex


class StubRAGIndex(RAGIndex):
    """Placeholder RAG index that documents the intended indexing flow."""

    async def index_chunks(self, chunks: list[FullTextChunk]) -> int:
        raise NotImplementedError(
            "Full-text RAG indexing is not yet implemented. "
            "Future versions will embed chunks and persist vectors for "
            "session-scoped similarity search."
        )

    async def search(self, query: str, *, top_k: int = 5) -> list[FullTextChunk]:
        raise NotImplementedError(
            "Full-text RAG search is not yet implemented. "
            "Future versions will retrieve the top-k chunks by embedding similarity."
        )
