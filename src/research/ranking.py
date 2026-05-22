# -*- coding: utf-8 -*-
"""Weighted multi-signal paper ranking."""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from ..core.context import PipelineContext, StageResult
from ..embeddings.base import EmbeddingProvider
from ..retrieval.models import RankedPaper, RetrievedPaper
from .canonical_works import CanonicalWork, load_canonical_works, match_canonical_work
from .embedding_context import store_ranking_embedding_result
from .metadata_sanity import sanitize_papers_metadata

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

_GENERIC_QUERY_TERMS = frozenset(
    {
        "mechanism",
        "mechanisms",
        "method",
        "methods",
        "approach",
        "approaches",
        "application",
        "applications",
        "model",
        "models",
        "system",
        "systems",
        "based",
        "using",
        "recent",
    }
)


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


def _paper_text_lower(paper: RetrievedPaper) -> str:
    return _paper_text(paper).lower()


def _core_query_terms(query_terms: set[str]) -> list[str]:
    return sorted(term for term in query_terms if term not in _GENERIC_QUERY_TERMS)


def _term_matches_text(term: str, text: str) -> bool:
    if term in text:
        return True
    if term.endswith("s") and term[:-1] in text:
        return True
    if f"{term}s" in text:
        return True
    return False


def applies_domain_penalty(query: str, paper: RetrievedPaper) -> bool:
    """Return True when a multi-concept query is only partially matched."""
    query_terms = _extract_query_terms(query)
    core_terms = _core_query_terms(query_terms)
    if len(core_terms) < 2:
        return False

    text = _paper_text_lower(paper)
    matched_core = [term for term in core_terms if _term_matches_text(term, text)]
    return len(matched_core) < len(core_terms)


def embedding_outlier(
    embedding_sim: float | None,
    top_k_mean_sim: float | None,
    outlier_gap: float,
) -> bool:
    """Return True when a paper's embedding similarity is far below the corpus top-k mean."""
    if embedding_sim is None or top_k_mean_sim is None:
        return False
    return embedding_sim < top_k_mean_sim - outlier_gap


def keyword_collision(
    paper: RetrievedPaper,
    query_terms: set[str],
    embedding_sim: float | None,
    max_sim: float,
) -> bool:
    """Return True when keyword overlap is high but semantic similarity is low."""
    if embedding_sim is None:
        return False
    overlap = signal_keyword_overlap(paper, query_terms)
    if overlap is None or overlap < 0.5:
        return False
    return embedding_sim < max_sim


def _top_k_mean_embedding_similarity(
    embedding_sims: list[float | None],
    top_k: int = 5,
) -> float | None:
    valid = [sim for sim in embedding_sims if sim is not None]
    if not valid:
        return None
    top_values = sorted(valid, reverse=True)[:top_k]
    return sum(top_values) / len(top_values)


def canonical_score_boost(
    paper: RetrievedPaper,
    works: list[CanonicalWork],
    boost: float,
) -> float:
    """Return a capped score boost when the paper matches a canonical registry entry."""
    if boost <= 0.0 or not works:
        return 0.0
    if match_canonical_work(paper.title, works) is None:
        return 0.0
    return boost


def signal_keyword_overlap(paper: RetrievedPaper, query_terms: set[str]) -> float | None:
    if not query_terms:
        return None

    paper_words = set(re.findall(r"\b\w+\b", _paper_text(paper).lower()))
    matches = query_terms.intersection(paper_words)
    if not matches:
        return 0.0
    return min(len(matches) / len(query_terms), 1.0)


def signal_semantic_relevance(
    paper: RetrievedPaper,
    query_terms: set[str],
    query_embedding: np.ndarray | None = None,
    paper_embedding: np.ndarray | None = None,
    embedder: EmbeddingProvider | None = None,
) -> float | None:
    if (
        query_embedding is not None
        and paper_embedding is not None
        and embedder is not None
    ):
        similarity = embedder.similarity(query_embedding, paper_embedding)
        return max(min(similarity, 1.0), 0.0)

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
    domain_penalty: float = 0.5,
    outlier_embedding_gap: float = 0.12,
    keyword_collision_max_sim: float = 0.40,
    top_k_mean_embedding_sim: float | None = None,
    canonical_boost: float = 0.0,
    canonical_works: list[CanonicalWork] | None = None,
) -> RankedPaper:
    query_terms = _extract_query_terms(query)
    embedding_sim = signal_embedding_similarity(
        paper,
        query_embedding,
        paper_embedding,
        embedder,
    )
    signals: dict[str, float | None] = {
        "semantic_relevance": signal_semantic_relevance(
            paper,
            query_terms,
            query_embedding=query_embedding,
            paper_embedding=paper_embedding,
            embedder=embedder,
        ),
        "citation_count": signal_citation_count(paper, papers),
        "recency": signal_recency(paper),
        "venue_quality": signal_venue_quality(paper),
        "abstract_completeness": signal_abstract_completeness(paper),
        "keyword_overlap": signal_keyword_overlap(paper, query_terms),
        "author_prominence": signal_author_prominence(paper),
        "embedding_similarity": embedding_sim,
    }

    available = {name: value for name, value in signals.items() if value is not None}
    active = _active_weights(weights, available)
    rank_score = sum(active[name] * available[name] for name in available)

    penalties: list[str] = []
    if applies_domain_penalty(query, paper):
        rank_score *= domain_penalty
        penalties.append("concept_coverage")
    if embedding_outlier(embedding_sim, top_k_mean_embedding_sim, outlier_embedding_gap):
        rank_score *= domain_penalty
        penalties.append("embedding_outlier")
    if keyword_collision(paper, query_terms, embedding_sim, keyword_collision_max_sim):
        rank_score *= domain_penalty
        penalties.append("keyword_collision")

    boost = canonical_score_boost(paper, canonical_works or [], canonical_boost)
    if boost > 0.0:
        rank_score = min(rank_score + boost, 1.0)

    breakdown = {name: round(value, 4) for name, value in available.items()}
    if penalties:
        for penalty_name in penalties:
            breakdown[f"penalty_{penalty_name}"] = 1.0
        breakdown["domain_penalty_multiplier"] = round(domain_penalty, 4)
    if boost > 0.0:
        breakdown["canonical_boost"] = round(boost, 4)

    return RankedPaper(
        paper=paper,
        rank_score=round(rank_score, 4),
        score_breakdown=breakdown,
    )


@dataclass(frozen=True)
class RankPapersResult:
    """Ranking output plus optional embedding artifacts for downstream stages."""

    ranked: list[RankedPaper]
    query_embedding: np.ndarray | None = None
    paper_embeddings: dict[str, np.ndarray] | None = None


def rank_papers(
    papers: list[RetrievedPaper],
    query: str,
    config: RankingConfig | None = None,
    embedder: EmbeddingProvider | None = None,
) -> RankPapersResult:
    """Rank papers using configurable weighted signals."""
    if config is None:
        from ..config.settings import get_settings

        config = get_settings().ranking

    if not papers:
        return RankPapersResult(ranked=[])

    canonical_works = load_canonical_works()
    papers = sanitize_papers_metadata(papers)

    query_embedding: np.ndarray | None = None
    paper_vectors: list[np.ndarray | None] = [None] * len(papers)
    if embedder is not None:
        texts = [_paper_text(paper) for paper in papers]
        vectors = embedder.embed_texts([query, *texts])
        query_embedding = vectors[0]
        paper_vectors = list(vectors[1:])

    embedding_sims: list[float | None] = [
        signal_embedding_similarity(
            paper,
            query_embedding,
            paper_vectors[index],
            embedder,
        )
        if embedder is not None
        else None
        for index, paper in enumerate(papers)
    ]
    top_k_mean_embedding_sim = _top_k_mean_embedding_similarity(embedding_sims)

    ranked = [
        score_paper(
            paper=paper,
            query=query,
            papers=papers,
            weights=config.weights,
            query_embedding=query_embedding,
            paper_embedding=paper_vectors[index],
            embedder=embedder,
            domain_penalty=config.domain_penalty_multiplier,
            outlier_embedding_gap=config.outlier_embedding_gap,
            keyword_collision_max_sim=config.keyword_collision_max_sim,
            top_k_mean_embedding_sim=top_k_mean_embedding_sim,
            canonical_boost=config.canonical_boost,
            canonical_works=canonical_works,
        )
        for index, paper in enumerate(papers)
    ]
    ranked.sort(key=lambda item: item.rank_score, reverse=True)
    top_ranked = ranked[: config.top_k]

    paper_embeddings: dict[str, np.ndarray] | None = None
    if query_embedding is not None:
        id_to_vector = {
            paper.paper_id: paper_vectors[index]
            for index, paper in enumerate(papers)
            if paper_vectors[index] is not None
        }
        paper_embeddings = {
            item.paper.paper_id: id_to_vector[item.paper.paper_id]
            for item in top_ranked
            if item.paper.paper_id in id_to_vector
        } or None

    return RankPapersResult(
        ranked=top_ranked,
        query_embedding=query_embedding,
        paper_embeddings=paper_embeddings or None,
    )


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
        if embedder is None:
            from ..embeddings import try_create_embedding_provider

            embedder = try_create_embedding_provider(ctx.config.embedding)
            if embedder is None and ctx.config.ranking.weights.embedding_similarity > 0:
                warnings.append(
                    "Embedding similarity ranking skipped: sentence-transformers is not installed. "
                    "Run: pipenv install"
                )

        try:
            ranking_result = rank_papers(
                papers=data,
                query=ctx.query,
                config=ctx.config.ranking,
                embedder=embedder,
            )
        except ImportError as exc:
            warnings.append(f"Ranking failed ({exc}); using keyword-only fallback")
            ranking_result = rank_papers(
                papers=data,
                query=ctx.query,
                config=ctx.config.ranking,
                embedder=None,
            )

        ranked = ranking_result.ranked
        store_ranking_embedding_result(
            ctx,
            ranking_result.query_embedding,
            ranking_result.paper_embeddings,
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
