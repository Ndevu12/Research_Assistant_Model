# -*- coding: utf-8 -*-
"""Paper deduplication by metadata keys and embedding similarity."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import TYPE_CHECKING

import numpy as np

from ..core.context import PipelineContext, StageResult
from ..embeddings.base import EmbeddingProvider
from ..research.metadata_sanity import metadata_quality_key, sanitize_papers_metadata
from .models import RetrievedPaper

if TYPE_CHECKING:
    from ..config.settings import DeduplicationConfig


def normalize_title(title: str) -> str:
    """Normalize a paper title for comparison."""
    normalized = title.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9 ]+", "", normalized)
    return normalized


def _union_find_parent(parent: list[int], index: int) -> int:
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def _union_find_merge(parent: list[int], left: int, right: int) -> None:
    left_root = _union_find_parent(parent, left)
    right_root = _union_find_parent(parent, right)
    if left_root != right_root:
        parent[left_root] = right_root


def _select_best_duplicate(candidates: list[RetrievedPaper]) -> RetrievedPaper:
    """Keep the highest-quality record from a duplicate cluster."""
    return max(candidates, key=metadata_quality_key)


def dedupe_by_metadata(papers: list[RetrievedPaper]) -> list[RetrievedPaper]:
    """Remove duplicate papers based on DOI or normalized title.

    Duplicate clusters are merged by keeping the highest-quality record.
    Generic metadata checks are applied before grouping.
    """
    if not papers:
        return []

    sanitized = sanitize_papers_metadata(papers)
    parent = list(range(len(sanitized)))
    title_index: dict[str, int] = {}
    doi_index: dict[str, int] = {}

    for index, paper in enumerate(sanitized):
        title_key = normalize_title(paper.title)
        if title_key in title_index:
            _union_find_merge(parent, index, title_index[title_key])
        else:
            title_index[title_key] = index

        if paper.doi:
            doi_key = paper.doi.lower().strip()
            if doi_key in doi_index:
                _union_find_merge(parent, index, doi_index[doi_key])
            else:
                doi_index[doi_key] = index

    clusters: dict[int, list[int]] = defaultdict(list)
    for index in range(len(sanitized)):
        clusters[_union_find_parent(parent, index)].append(index)

    output: list[RetrievedPaper] = []
    emitted_roots: set[int] = set()
    for index, paper in enumerate(sanitized):
        root = _union_find_parent(parent, index)
        if root in emitted_roots:
            continue
        emitted_roots.add(root)
        cluster = [sanitized[member_index] for member_index in clusters[root]]
        if len(cluster) == 1:
            output.append(paper)
        else:
            output.append(_select_best_duplicate(cluster))
    return output


def _paper_preference_key(paper: RetrievedPaper) -> tuple[int, int, int, int, int]:
    """Rank duplicates; higher values are preferred to keep."""
    return metadata_quality_key(paper)


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
