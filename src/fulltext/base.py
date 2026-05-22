# -*- coding: utf-8 -*-
"""Full-text provider abstractions for future PDF ingestion and RAG."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field


class FullTextDocument(BaseModel):
    """Downloaded or extracted full-text document metadata."""

    paper_id: str
    source_url: str | None = None
    local_path: Path | None = None
    text: str | None = None
    page_count: int | None = None
    metadata: dict = Field(default_factory=dict)


class FullTextChunk(BaseModel):
    """A chunk of full text suitable for embedding and retrieval."""

    paper_id: str
    chunk_index: int
    text: str
    start_page: int | None = None
    end_page: int | None = None
    metadata: dict = Field(default_factory=dict)


class PDFDownloader(ABC):
    """Download PDFs for papers with open-access URLs.

    Future flow:
    1. Resolve PDF URL from ``RetrievedPaper`` metadata (DOI, arXiv, CORE).
    2. Download to a cache directory keyed by paper ID.
    3. Return ``FullTextDocument`` with local path for downstream parsing.
    """

    @abstractmethod
    async def download(self, paper_id: str, url: str) -> FullTextDocument:
        """Download a PDF and return document metadata."""


class TextChunker(ABC):
    """Split full text into overlapping chunks for embedding.

    Future flow:
    1. Accept extracted plain text from PDF parsing.
    2. Split by token/character windows with overlap.
    3. Attach page numbers when available.
    """

    @abstractmethod
    def chunk(self, document: FullTextDocument) -> list[FullTextChunk]:
        """Split a document into retrieval-ready chunks."""


class RAGIndex(ABC):
    """Vector index over full-text chunks for grounded Q&A.

    Future flow:
    1. Embed chunks via ``EmbeddingProvider``.
    2. Persist vectors (SQLite blobs or dedicated vector store).
    3. Support similarity search scoped to a research session.
    """

    @abstractmethod
    async def index_chunks(self, chunks: list[FullTextChunk]) -> int:
        """Index chunks and return the number indexed."""

    @abstractmethod
    async def search(self, query: str, *, top_k: int = 5) -> list[FullTextChunk]:
        """Return the most relevant chunks for a query."""
