# -*- coding: utf-8 -*-
"""Section-aware chunking of extracted full text."""

from __future__ import annotations

from .base import FullTextChunk, FullTextDocument, TextChunker


class SectionAwareChunker(TextChunker):
    """Packs paragraphs into overlapping chunks that respect section marks.

    Section markers (``## Heading`` lines emitted by the parser) start a new
    chunk and tag every chunk that follows until the next marker, so a
    retrieved passage can say which part of the paper it came from.
    """

    def __init__(self, max_chars: int = 1400, overlap_chars: int = 200) -> None:
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk(self, document: FullTextDocument) -> list[FullTextChunk]:
        if not document.text:
            return []

        chunks: list[FullTextChunk] = []
        current_parts: list[str] = []
        current_length = 0
        section = "body"

        def flush() -> None:
            nonlocal current_parts, current_length
            text = "\n".join(current_parts).strip()
            if len(text) >= 200:
                chunks.append(
                    FullTextChunk(
                        paper_id=document.paper_id,
                        chunk_index=len(chunks),
                        text=text,
                        metadata={"section": section},
                    )
                )
            if text and self.overlap_chars > 0:
                tail = text[-self.overlap_chars :]
                current_parts = [tail]
                current_length = len(tail)
            else:
                current_parts = []
                current_length = 0

        for paragraph in document.text.split("\n\n"):
            stripped = paragraph.strip()
            if not stripped:
                continue

            if stripped.startswith("## "):
                flush()
                current_parts = []
                current_length = 0
                section = stripped[3:].strip().lower()
                continue

            if current_length + len(stripped) > self.max_chars and current_parts:
                flush()

            current_parts.append(stripped)
            current_length += len(stripped)

        text = "\n".join(current_parts).strip()
        if len(text) >= 200:
            chunks.append(
                FullTextChunk(
                    paper_id=document.paper_id,
                    chunk_index=len(chunks),
                    text=text,
                    metadata={"section": section},
                )
            )
        return chunks
