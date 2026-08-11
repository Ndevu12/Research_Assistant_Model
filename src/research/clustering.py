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
from .embedding_context import get_paper_embeddings
from .text_utils import LABEL_STOP_WORDS

if TYPE_CHECKING:
    from ..config.settings import ClusteringConfig


def _paper_text(paper: RankedPaper) -> str:
    parts = [paper.paper.title]
    if paper.paper.abstract:
        parts.append(paper.paper.abstract)
    return " ".join(parts)


def _label_cluster(papers: list[RankedPaper]) -> tuple[str, str]:
    words: list[str] = []
    for ranked in papers:
        tokens = re.findall(r"\b[a-z]{4,}\b", ranked.paper.title.lower())
        words.extend(token for token in tokens if token not in LABEL_STOP_WORDS)

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


def _extract_tokens(text: str) -> list[str]:
    tokens = re.findall(r"\b[a-z]{4,}\b", text.lower())
    return [token for token in tokens if token not in LABEL_STOP_WORDS]


def _macro_cluster_count(noise_count: int, config: ClusteringConfig) -> int:
    if noise_count <= 1:
        return noise_count
    return min(config.max_macro_clusters, noise_count)


def _macro_cluster(papers: list[RankedPaper]) -> PaperCluster:
    theme, summary = _label_cluster(papers)
    return PaperCluster(
        theme=f"Theme: {theme}",
        summary=summary,
        paper_ids=[paper.paper.paper_id for paper in papers],
    )


def _merge_noise_into_macro_clusters(
    noise_papers: list[RankedPaper],
    config: ClusteringConfig,
) -> list[PaperCluster]:
    """Group HDBSCAN noise papers into keyword macro-themes instead of singletons."""
    if not noise_papers:
        return []

    if len(noise_papers) == 1:
        return [_macro_cluster(noise_papers)]

    doc_tokens = [_extract_tokens(_paper_text(paper)) for paper in noise_papers]
    vocabulary = sorted({token for tokens in doc_tokens for token in tokens})
    if not vocabulary:
        return [_macro_cluster(noise_papers)]

    term_index = {term: index for index, term in enumerate(vocabulary)}
    matrix = np.zeros((len(noise_papers), len(vocabulary)), dtype=np.float32)
    for row, tokens in enumerate(doc_tokens):
        counts = Counter(tokens)
        for term, count in counts.items():
            matrix[row, term_index[term]] = float(count)

    cluster_count = _macro_cluster_count(len(noise_papers), config)
    if cluster_count <= 1:
        return [_macro_cluster(noise_papers)]

    try:
        from sklearn.cluster import KMeans

        labels = KMeans(n_clusters=cluster_count, random_state=0, n_init=10).fit_predict(matrix)
    except Exception:
        return [_macro_cluster(noise_papers)]

    grouped: dict[int, list[RankedPaper]] = {}
    for index, label in enumerate(labels):
        grouped.setdefault(int(label), []).append(noise_papers[index])

    return [_macro_cluster(group) for group in grouped.values()]


def cluster_papers(
    ranked_papers: list[RankedPaper],
    config: ClusteringConfig | None = None,
    embedder: EmbeddingProvider | None = None,
    paper_embeddings: dict[str, np.ndarray] | None = None,
) -> list[PaperCluster]:
    """Cluster ranked papers into thematic groups."""
    if config is None:
        from ..config.settings import get_settings

        config = get_settings().clustering

    if not ranked_papers:
        return []

    if len(ranked_papers) < config.min_cluster_size:
        return _fallback_single_cluster(ranked_papers)

    from .embedding_context import resolve_paper_embedding_matrix

    embeddings = resolve_paper_embedding_matrix(ranked_papers, paper_embeddings)

    if embeddings is None:
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

    noise_papers = clusters.pop(-1, [])
    noise_ratio = len(noise_papers) / len(ranked_papers)

    output: list[PaperCluster] = []
    for label in sorted(clusters):
        group = clusters[label]
        theme, summary = _label_cluster(group)
        output.append(
            PaperCluster(
                theme=theme,
                summary=summary,
                paper_ids=[paper.paper.paper_id for paper in group],
            )
        )

    if noise_papers:
        if noise_ratio > config.noise_merge_threshold:
            output.extend(_merge_noise_into_macro_clusters(noise_papers, config))
        else:
            for ranked in noise_papers:
                theme, summary = _label_cluster([ranked])
                output.append(
                    PaperCluster(
                        theme=f"Unclustered: {theme}",
                        summary=summary,
                        paper_ids=[ranked.paper.paper_id],
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
            paper_embeddings=get_paper_embeddings(ctx) or None,
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
