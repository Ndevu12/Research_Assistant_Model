# -*- coding: utf-8 -*-
"""Paper deduplication by metadata keys and embedding similarity."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

import numpy as np

from ..core.context import PipelineContext, StageResult
from ..embeddings.base import EmbeddingProvider
from .models import RetrievedPaper

if TYPE_CHECKING:
    from ..config.settings import DeduplicationConfig


def normalize_title(title: str) -> str:
    """Normalize a paper title for comparison."""
    normalized = title.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9 ]+", "", normalized)
    return normalized


def dedupe_by_metadata(papers: list[RetrievedPaper]) -> list[RetrievedPaper]:
    """Remove duplicate papers based on DOI or normalized title."""
    seen_dois: set[str] = set()
    seen_titles: set[str] = set()
    output: list[RetrievedPaper] = []
    for paper in papers:
        doi_key = paper.doi.lower().strip() if paper.doi else None
        title_key = normalize_title(paper.title)

        if doi_key and doi_key in seen_dois:
            continue
        if title_key in seen_titles:
            continue

        if doi_key:
            seen_dois.add(doi_key)
        seen_titles.add(title_key)
        output.append(paper)
    return output


def _paper_preference_key(paper: RetrievedPaper) -> tuple[int, int, int]:
    """Rank duplicates; higher values are preferred to keep."""
    abstract_len = len(paper.abstract or "")
    citation_count = paper.citation_count or 0
    metadata_score = int(bool(paper.doi)) + int(bool(paper.url))
    return (citation_count, abstract_len, metadata_score)


def _paper_dedup_text(paper: RetrievedPaper) -> str:
    parts = [paper.title]
    if paper.abstract:
        parts.append(paper.abstract[:500])
    return " ".join(parts)


def dedupe_by_embedding(
    papers: list[RetrievedPaper],
    embedder: EmbeddingProvider,
    threshold: float,
) -> tuple[list[RetrievedPaper], int]:
    """Remove near-duplicate papers using cosine similarity on embeddings."""
    if len(papers) < 2:
        return papers, 0

    texts = [_paper_dedup_text(paper) for paper in papers]
    embeddings = embedder.embed_texts(texts)
    removed = 0
    keep_indices: list[int] = []

    for index, paper in enumerate(papers):
        duplicate = False
        for kept_index in keep_indices:
            similarity = embedder.similarity(embeddings[index], embeddings[kept_index])
            if similarity >= threshold:
                duplicate = True
                removed += 1
                if _paper_preference_key(paper) > _paper_preference_key(papers[kept_index]):
                    keep_indices[keep_indices.index(kept_index)] = index
                break
        if not duplicate:
            keep_indices.append(index)

    deduped = [papers[index] for index in keep_indices]
    return deduped, removed


def deduplicate_papers(
    papers: list[RetrievedPaper],
    config: DeduplicationConfig | None = None,
    embedder: EmbeddingProvider | None = None,
) -> tuple[list[RetrievedPaper], dict[str, int]]:
    """Deduplicate papers by DOI/title and optional embedding similarity."""
    if config is None:
        from ..config.settings import get_settings

        config = get_settings().deduplication

    stats = {
        "input_count": len(papers),
        "metadata_removed": 0,
        "embedding_removed": 0,
        "output_count": 0,
    }

    metadata_deduped = dedupe_by_metadata(papers)
    stats["metadata_removed"] = len(papers) - len(metadata_deduped)

    output = metadata_deduped
    if config.enabled and config.enable_embedding_dedup and len(output) >= 2:
        if embedder is None:
            from ..embeddings import create_embedding_provider

            embedder = create_embedding_provider()
        output, embedding_removed = dedupe_by_embedding(
            output,
            embedder=embedder,
            threshold=config.embedding_similarity_threshold,
        )
        stats["embedding_removed"] = embedding_removed

    stats["output_count"] = len(output)
    return output, stats


class DeduplicationStage:
    """Pipeline stage that deduplicates retrieved papers."""

    name = "deduplication"

    def __init__(self, embedder: EmbeddingProvider | None = None) -> None:
        self.embedder = embedder

    async def run(
        self,
        ctx: PipelineContext,
        data: list[RetrievedPaper],
    ) -> StageResult[list[RetrievedPaper]]:
        started = time.perf_counter()
        warnings: list[str] = []

        embedder = self.embedder
        if (
            embedder is None
            and ctx.config.deduplication.enabled
            and ctx.config.deduplication.enable_embedding_dedup
        ):
            from ..embeddings import try_create_embedding_provider

            embedder = try_create_embedding_provider(ctx.config.embedding)
            if embedder is None:
                warnings.append(
                    "Embedding deduplication skipped: sentence-transformers is not installed. "
                    "Run: pipenv install"
                )

        deduped, stats = deduplicate_papers(
            papers=data,
            config=ctx.config.deduplication,
            embedder=embedder,
        )

        duration_ms = (time.perf_counter() - started) * 1000
        ctx.set_artifact("deduplication_stats", stats)

        return StageResult(
            output=deduped,
            duration_ms=duration_ms,
            metrics=stats,
            warnings=warnings,
        )
