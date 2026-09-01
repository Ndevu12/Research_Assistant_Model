# -*- coding: utf-8 -*-
"""Pipeline stage that grounds top papers in their full text.

For the relevance-filtered papers, the stage resolves open-access PDF
URLs, downloads and parses the PDFs, chunks the text section-aware, and
retrieves the query-relevant passages per paper. The passages land in the
``fulltext_passages`` artifact, which synthesis uses to ground extractions
and reports use to show verbatim evidence.

Everything is best-effort and budgeted: closed-access papers, failed
downloads, or a missing PDF backend reduce coverage, never break the run.
"""

from __future__ import annotations

import time

import aiohttp

from ..core.context import PipelineContext, StageResult
from ..retrieval.models import RankedPaper
from ..utils.logging_system import logger
from .base import FullTextChunk
from .chunker import SectionAwareChunker
from .downloader import CachingPDFDownloader
from .rag import InMemoryFulltextIndex
from .resolver import resolve_pdf_url

PASSAGES_ARTIFACT = "fulltext_passages"
SECTIONS_ARTIFACT = "fulltext_sections"


class FulltextStage:
    """Download, parse, chunk, and retrieve grounded passages."""

    name = "fulltext"

    def __init__(
        self,
        downloader: CachingPDFDownloader | None = None,
        chunker: SectionAwareChunker | None = None,
        index: InMemoryFulltextIndex | None = None,
    ) -> None:
        self.downloader = downloader
        self.chunker = chunker
        self.index = index

    async def run(
        self,
        ctx: PipelineContext,
        data: list[RankedPaper],
    ) -> StageResult[list[RankedPaper]]:
        started = time.perf_counter()
        config = ctx.config.fulltext
        warnings: list[str] = []

        def _passthrough(**metrics: object) -> StageResult[list[RankedPaper]]:
            return StageResult(
                output=data,
                duration_ms=(time.perf_counter() - started) * 1000,
                metrics={"papers_with_passages": 0, **metrics},
                warnings=warnings,
            )

        if not config.enabled or not data:
            return _passthrough(skipped=True)

        try:
            import pymupdf  # noqa: F401
        except ImportError:
            warnings.append(
                "Full-text grounding skipped: pymupdf is not installed. Run: pipenv install"
            )
            return _passthrough()

        from .parser import extract_document

        candidates = [
            (ranked.paper, resolve_pdf_url(ranked.paper))
            for ranked in data[: config.max_papers]
        ]
        resolvable = [(paper, url) for paper, url in candidates if url]
        if not resolvable:
            return _passthrough(pdfs_resolved=0)

        downloader = self.downloader or CachingPDFDownloader(
            cache_dir=config.cache_dir,
            max_bytes=config.max_pdf_mb * 1024 * 1024,
            timeout_seconds=config.request_timeout_seconds,
        )
        chunker = self.chunker or SectionAwareChunker(
            max_chars=config.chunk_chars,
            overlap_chars=config.chunk_overlap,
        )

        chunks_by_paper: dict[str, list[FullTextChunk]] = {}
        sections_by_paper: dict[str, dict[str, int]] = {}
        downloaded = 0

        async with aiohttp.ClientSession() as session:
            for paper, url in resolvable:
                try:
                    document = await downloader.download(paper.paper_id, url, session=session)
                    parsed = extract_document(paper.paper_id, document.local_path)
                    chunks = chunker.chunk(parsed)
                except Exception as exc:
                    logger.info("Full text unavailable for %s: %s", paper.title[:60], exc)
                    continue
                downloaded += 1
                if chunks:
                    chunks_by_paper[paper.paper_id] = chunks
                    sections_by_paper[paper.paper_id] = dict(
                        parsed.metadata.get("sections") or {}
                    )

        if not chunks_by_paper:
            return _passthrough(pdfs_resolved=len(resolvable), pdfs_downloaded=downloaded)

        index = self.index
        if index is None:
            from ..embeddings import try_create_embedding_provider

            index = InMemoryFulltextIndex(
                embedder=try_create_embedding_provider(ctx.config.embedding)
            )

        total_chunks = 0
        for chunks in chunks_by_paper.values():
            total_chunks += await index.index_chunks(chunks)

        passages: dict[str, list[str]] = {}
        for paper_id in chunks_by_paper:
            top = await index.search(
                ctx.query,
                top_k=config.top_chunks_per_paper,
                paper_id=paper_id,
            )
            if top:
                passages[paper_id] = [chunk.text for chunk in top]

        ctx.set_artifact(PASSAGES_ARTIFACT, passages)
        ctx.set_artifact(SECTIONS_ARTIFACT, sections_by_paper)

        return StageResult(
            output=data,
            duration_ms=(time.perf_counter() - started) * 1000,
            metrics={
                "pdfs_resolved": len(resolvable),
                "pdfs_downloaded": downloaded,
                "chunks_indexed": total_chunks,
                "papers_with_passages": len(passages),
            },
            warnings=warnings,
        )
