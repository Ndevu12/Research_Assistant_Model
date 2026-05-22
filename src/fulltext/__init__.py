# -*- coding: utf-8 -*-
"""Full-text ingestion architecture (Phase 3 interfaces only)."""

from .base import FullTextChunk, FullTextDocument, PDFDownloader, RAGIndex, TextChunker
from .chunker import StubTextChunker
from .downloader import StubPDFDownloader
from .rag import StubRAGIndex

__all__ = [
    "FullTextChunk",
    "FullTextDocument",
    "PDFDownloader",
    "RAGIndex",
    "StubPDFDownloader",
    "StubRAGIndex",
    "StubTextChunker",
    "TextChunker",
]
