# -*- coding: utf-8 -*-
"""Weighted multi-signal paper ranking."""

from __future__ import annotations

import math
import re
import time
from typing import TYPE_CHECKING

import numpy as np

from ..core.context import PipelineContext, StageResult
from ..embeddings.base import EmbeddingProvider
from ..retrieval.models import RankedPaper, RetrievedPaper

if TYPE_CHECKING:
    from ..config.settings import RankingConfig, RankingWeights

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
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "paper",
    "papers",
    "research",
    "study",
    "studies",
}

_KNOWN_VENUES = {
    "neurips",
    "nips",
    "icml",
    "iclr",
    "acl",
    "emnlp",
    "naacl",
    "cvpr",
    "iccv",
    "eccv",
    "aaai",
    "ijcai",
    "nature",
    "science",
    "jmlr",
}


def _extract_query_terms(query: str) -> set[str]:
    words = re.findall(r"\b\w+\b", query.lower())
    return {word for word in words if word not in _STOP_WORDS and len(word) > 2}


def _paper_text(paper: RetrievedPaper) -> str:
    parts = [paper.title]
    if paper.abstract:
        parts.append(paper.abstract)
    if paper.keywords:
        parts.extend(paper.keywords)
    if paper.authors:
        parts.extend(paper.authors)
    return " ".join(parts)


def signal_keyword_overlap(paper: RetrievedPaper, query_terms: set[str]) -> float | None:
    if not query_terms:
        return None

    paper_words = set(re.findall(r"\b\w+\b", _paper_text(paper).lower()))
    matches = query_terms.intersection(paper_words)
    if not matches:
        return 0.0
    return min(len(matches) / len(query_terms), 1.0)


def signal_semantic_relevance(paper: RetrievedPaper, query_terms: set[str]) -> float | None:
    overlap = signal_keyword_overlap(paper, query_terms)
    if overlap is None:
        return None

    title_words = set(re.findall(r"\b\w+\b", paper.title.lower()))
    title_matches = len(query_terms.intersection(title_words))
    title_boost = (title_matches / len(query_terms)) * 0.3 if query_terms else 0.0
    return min(overlap * 0.7 + title_boost, 1.0)


def signal_citation_count(paper: RetrievedPaper, papers: list[RetrievedPaper]) -> float | None:
    if paper.citation_count is None:
        return None
    counts = [p.citation_count or 0 for p in papers]
    max_count = max(counts) if counts else 0
    if max_count <= 0:
        return 0.0 if paper.citation_count == 0 else 1.0
    normalized = math.log1p(paper.citation_count) / math.log1p(max_count)
    return min(normalized, 1.0)


def signal_recency(paper: RetrievedPaper, current_year: int = 2026) -> float | None:
    if paper.year is None:
        return None
    age = max(current_year - paper.year, 0)
    if age >= 20:
        return 0.1
    return max(1.0 - (age / 20.0), 0.0)


def signal_venue_quality(paper: RetrievedPaper) -> float | None:
    if not paper.venue:
        return None
    venue_lower = paper.venue.lower()
    if any(name in venue_lower for name in _KNOWN_VENUES):
        return 1.0
    if "journal" in venue_lower or "proceedings" in venue_lower:
        return 0.6
    return 0.4


def signal_abstract_completeness(paper: RetrievedPaper) -> float | None:
    if paper.abstract is None:
        return 0.0
    length = len(paper.abstract.strip())
    if length == 0:
        return 0.0
    if length >= 1200:
        return 1.0
    return min(length / 1200.0, 1.0)


def signal_author_prominence(paper: RetrievedPaper) -> float | None:
    if not paper.authors:
        return None
    author_count = len(paper.authors)
    if author_count >= 5:
        return 1.0
    return min(author_count / 5.0, 1.0)


def signal_embedding_similarity(
    paper: RetrievedPaper,
    query_embedding: np.ndarray | None,
    paper_embedding: np.ndarray | None,
    embedder: EmbeddingProvider | None,
) -> float | None:
    if query_embedding is None or paper_embedding is None or embedder is None:
        return None
    similarity = embedder.similarity(query_embedding, paper_embedding)
    return max(min(similarity, 1.0), 0.0)


def _active_weights(
    weights: RankingWeights,
    available_signals: dict[str, float],
) -> dict[str, float]:
    raw = {name: getattr(weights, name) for name in available_signals}
    total = sum(raw.values())
    if total <= 0:
        uniform = 1.0 / len(available_signals)
        return {name: uniform for name in available_signals}
    return {name: value / total for name, value in raw.items()}


def score_paper(
    paper: RetrievedPaper,
    query: str,
    papers: list[RetrievedPaper],
    weights: RankingWeights,
    query_embedding: np.ndarray | None = None,
    paper_embedding: np.ndarray | None = None,
    embedder: EmbeddingProvider | None = None,
) -> RankedPaper:
    query_terms = _extract_query_terms(query)
    signals: dict[str, float | None] = {
        "semantic_relevance": signal_semantic_relevance(paper, query_terms),
        "citation_count": signal_citation_count(paper, papers),
        "recency": signal_recency(paper),
        "venue_quality": signal_venue_quality(paper),
        "abstract_completeness": signal_abstract_completeness(paper),
        "keyword_overlap": signal_keyword_overlap(paper, query_terms),
        "author_prominence": signal_author_prominence(paper),
        "embedding_similarity": signal_embedding_similarity(
            paper,
            query_embedding,
            paper_embedding,
            embedder,
        ),
    }

    available = {name: value for name, value in signals.items() if value is not None}
    active = _active_weights(weights, available)
    rank_score = sum(active[name] * available[name] for name in available)
    breakdown = {name: round(value, 4) for name, value in available.items()}

    return RankedPaper(
        paper=paper,
        rank_score=round(rank_score, 4),
        score_breakdown=breakdown,
    )


def rank_papers(
    papers: list[RetrievedPaper],
    query: str,
    config: RankingConfig | None = None,
    embedder: EmbeddingProvider | None = None,
) -> list[RankedPaper]:
    """Rank papers using configurable weighted signals."""
    if config is None:
        from ..config.settings import get_settings

        config = get_settings().ranking

    if not papers:
        return []

    query_embedding: np.ndarray | None = None
    paper_embeddings: list[np.ndarray | None] = [None] * len(papers)
    if embedder is not None and config.weights.embedding_similarity > 0:
        texts = [_paper_text(paper) for paper in papers]
        vectors = embedder.embed_texts([query, *texts])
        query_embedding = vectors[0]
        paper_embeddings = list(vectors[1:])

    ranked = [
        score_paper(
            paper=paper,
            query=query,
            papers=papers,
            weights=config.weights,
            query_embedding=query_embedding,
            paper_embedding=paper_embeddings[index],
            embedder=embedder,
        )
        for index, paper in enumerate(papers)
    ]
    ranked.sort(key=lambda item: item.rank_score, reverse=True)
    return ranked[: config.top_k]


class RankingStage:
    """Pipeline stage that ranks deduplicated papers."""

    name = "ranking"

    def __init__(self, embedder: EmbeddingProvider | None = None) -> None:
        self.embedder = embedder

    async def run(
        self,
        ctx: PipelineContext,
        data: list[RetrievedPaper],
    ) -> StageResult[list[RankedPaper]]:
        started = time.perf_counter()
        warnings: list[str] = []

        embedder = self.embedder
        if embedder is None and ctx.config.ranking.weights.embedding_similarity > 0:
            from ..embeddings import try_create_embedding_provider

            embedder = try_create_embedding_provider(ctx.config.embedding)
            if embedder is None:
                warnings.append(
                    "Embedding similarity ranking skipped: sentence-transformers is not installed. "
                    "Run: pipenv install"
                )

        try:
            ranked = rank_papers(
                papers=data,
                query=ctx.query,
                config=ctx.config.ranking,
                embedder=embedder,
            )
        except ImportError as exc:
            warnings.append(f"Ranking failed ({exc}); using keyword-only fallback")
            ranked = rank_papers(
                papers=data,
                query=ctx.query,
                config=ctx.config.ranking,
                embedder=None,
            )

        duration_ms = (time.perf_counter() - started) * 1000
        top_score = ranked[0].rank_score if ranked else 0.0
        ctx.metrics.record_ranking(top_score=top_score)
        ctx.set_artifact("ranked_papers", ranked)

        return StageResult(
            output=ranked,
            duration_ms=duration_ms,
            metrics={
                "papers_ranked": len(ranked),
                "top_score": top_score,
            },
            warnings=warnings,
        )
