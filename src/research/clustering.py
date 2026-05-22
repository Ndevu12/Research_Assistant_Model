# -*- coding: utf-8 -*-
"""Thematic clustering of ranked papers using embeddings and HDBSCAN."""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import TYPE_CHECKING

import numpy as np

from ..core.context import PipelineContext, StageResult
from ..core.paper_adapters import ensure_ranked_papers
from ..embeddings.base import EmbeddingProvider
from ..retrieval.models import PaperCluster, RankedPaper

if TYPE_CHECKING:
    from ..config.settings import ClusteringConfig

_STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "using",
    "based",
    "via",
    "from",
}


def _paper_text(paper: RankedPaper) -> str:
    parts = [paper.paper.title]
    if paper.paper.abstract:
        parts.append(paper.paper.abstract)
    return " ".join(parts)


def _label_cluster(papers: list[RankedPaper]) -> tuple[str, str]:
    words: list[str] = []
    for ranked in papers:
        tokens = re.findall(r"\b[a-z]{4,}\b", ranked.paper.title.lower())
        words.extend(token for token in tokens if token not in _STOP_WORDS)

    if not words:
        return "General", "Related papers grouped by embedding similarity."

    counts = Counter(words)
    top_terms = [term for term, _ in counts.most_common(3)]
    theme = " / ".join(term.title() for term in top_terms)
    summary = f"Papers discussing {', '.join(top_terms)}."
    return theme, summary


def _cluster_with_hdbscan(
    embeddings: np.ndarray,
    config: ClusteringConfig,
) -> np.ndarray:
    import hdbscan

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=config.min_cluster_size,
        min_samples=config.min_samples,
        metric="euclidean",
    )
    return clusterer.fit_predict(embeddings)


def _fallback_single_cluster(papers: list[RankedPaper]) -> list[PaperCluster]:
    theme, summary = _label_cluster(papers)
    return [
        PaperCluster(
            theme=theme,
            summary=summary,
            paper_ids=[paper.paper.paper_id for paper in papers],
        )
    ]


def cluster_papers(
    ranked_papers: list[RankedPaper],
    config: ClusteringConfig | None = None,
    embedder: EmbeddingProvider | None = None,
) -> list[PaperCluster]:
    """Cluster ranked papers into thematic groups."""
    if config is None:
        from ..config.settings import get_settings

        config = get_settings().clustering

    if not ranked_papers:
        return []

    if len(ranked_papers) < config.min_cluster_size:
        return _fallback_single_cluster(ranked_papers)

    if embedder is None:
        from ..embeddings import try_create_embedding_provider

        embedder = try_create_embedding_provider()

    if embedder is None:
        return _fallback_single_cluster(ranked_papers)

    texts = [_paper_text(paper) for paper in ranked_papers]
    embeddings = embedder.embed_texts(texts)

    try:
        labels = _cluster_with_hdbscan(embeddings, config)
    except Exception:
        return _fallback_single_cluster(ranked_papers)

    clusters: dict[int, list[RankedPaper]] = {}
    for index, label in enumerate(labels):
        bucket = int(label)
        clusters.setdefault(bucket, []).append(ranked_papers[index])

    output: list[PaperCluster] = []
    for label in sorted(clusters):
        group = clusters[label]
        if label == -1:
            for ranked in group:
                theme, summary = _label_cluster([ranked])
                output.append(
                    PaperCluster(
                        theme=f"Unclustered: {theme}",
                        summary=summary,
                        paper_ids=[ranked.paper.paper_id],
                    )
                )
            continue

        theme, summary = _label_cluster(group)
        output.append(
            PaperCluster(
                theme=theme,
                summary=summary,
                paper_ids=[paper.paper.paper_id for paper in group],
            )
        )

    if not output:
        return _fallback_single_cluster(ranked_papers)

    return output


class ClusteringStage:
    """Pipeline stage that groups ranked papers into thematic clusters."""

    name = "clustering"

    def __init__(self, embedder: EmbeddingProvider | None = None) -> None:
        self.embedder = embedder

    async def run(
        self,
        ctx: PipelineContext,
        data: list[RankedPaper],
    ) -> StageResult[list[PaperCluster]]:
        started = time.perf_counter()
        warnings: list[str] = []

        ranked, adapter_warnings = ensure_ranked_papers(
            data,
            ctx.query,
            config=ctx.config.ranking,
        )
        warnings.extend(adapter_warnings)

        if not ranked:
            duration_ms = (time.perf_counter() - started) * 1000
            return StageResult(
                output=[],
                duration_ms=duration_ms,
                metrics={"num_clusters": 0},
                warnings=warnings,
            )

        embedder = self.embedder
        if embedder is None:
            from ..embeddings import try_create_embedding_provider

            embedder = try_create_embedding_provider(ctx.config.embedding)
            if embedder is None:
                warnings.append(
                    "Embedding clustering skipped: sentence-transformers is not installed. "
                    "Using single keyword-based theme group."
                )

        clusters = cluster_papers(
            ranked_papers=ranked,
            config=ctx.config.clustering,
            embedder=embedder,
        )

        duration_ms = (time.perf_counter() - started) * 1000
        ctx.metrics.record_clustering(num_clusters=len(clusters))
        ctx.set_artifact("paper_clusters", clusters)

        return StageResult(
            output=clusters,
            duration_ms=duration_ms,
            metrics={"num_clusters": len(clusters)},
            warnings=warnings,
        )
