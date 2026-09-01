# -*- coding: utf-8 -*-
"""Full-text ingestion: PDF resolution, parsing, chunking, and retrieval."""

from .base import FullTextChunk, FullTextDocument, PDFDownloader, RAGIndex, TextChunker
from .chunker import SectionAwareChunker
from .downloader import CachingPDFDownloader
from .rag import InMemoryFulltextIndex
from .resolver import resolve_pdf_url
from .stage import FulltextStage

__all__ = [
    "CachingPDFDownloader",
    "FullTextChunk",
    "FullTextDocument",
    "FulltextStage",
    "InMemoryFulltextIndex",
    "PDFDownloader",
    "RAGIndex",
    "SectionAwareChunker",
    "TextChunker",
    "resolve_pdf_url",
]
