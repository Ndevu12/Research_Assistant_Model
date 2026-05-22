# -*- coding: utf-8 -*-
"""Text chunking stubs for future full-text ingestion."""

from __future__ import annotations

from .base import FullTextChunk, FullTextDocument, TextChunker


class StubTextChunker(TextChunker):
    """Placeholder chunker that documents the intended chunking flow."""

    def chunk(self, document: FullTextDocument) -> list[FullTextChunk]:
        raise NotImplementedError(
            "Text chunking is not yet implemented. "
            "Future versions will split extracted PDF text into overlapping "
            "windows for embedding and RAG retrieval."
        )
