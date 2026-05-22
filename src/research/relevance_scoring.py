# -*- coding: utf-8 -*-
"""Post-ranking relevance filtering stage."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from ..core.context import PipelineContext, StageResult
from ..core.paper_adapters import ensure_ranked_papers
from ..retrieval.models import QueryUnderstandingResult, RankedPaper, RetrievedPaper
from .embedding_context import cosine_similarity, get_paper_embedding, get_query_embedding
from .query_expansion import extract_core_concepts

if TYPE_CHECKING:
    from ..config.settings import RelevanceScoringConfig

_GENERIC_CONCEPT_TERMS = frozenset(
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


def _term_matches_text(term: str, text: str) -> bool:
    if term in text:
        return True
    if term.endswith("s") and term[:-1] in text:
        return True
    if f"{term}s" in text:
        return True
    return False


def _core_concepts(query: str, ctx: PipelineContext) -> list[str]:
    understanding = ctx.get_artifact("query_understanding")
    if isinstance(understanding, QueryUnderstandingResult) and understanding.key_concepts:
        concepts = understanding.key_concepts
    else:
        concepts = extract_core_concepts(query)

    return [
        concept
        for concept in concepts
        if concept.lower() not in _GENERIC_CONCEPT_TERMS
    ]


def _concept_groups_match(
    paper: RetrievedPaper,
    concepts: list[str],
    *,
    mode: str,
) -> bool:
    if not concepts:
        return True

    title = paper.title.lower()
    abstract = (paper.abstract or "").lower()

    if mode != "any_group":
        text = " ".join(part for part in (title, abstract) if part)
        return all(_term_matches_text(concept, text) for concept in concepts)

    return all(
        _term_matches_text(concept, title) or _term_matches_text(concept, abstract)
        for concept in concepts
    )


def _combined_relevance_score(rank_score: float, embedding_similarity: float | None) -> float:
    if embedding_similarity is None:
        return rank_score
    return (rank_score + embedding_similarity) / 2.0


def compute_adaptive_embedding_floor(
    similarities: list[float],
    *,
    config: RelevanceScoringConfig,
    corpus_size: int,
) -> float:
    """Derive a corpus-relative embedding floor from similarity distribution."""
    if not similarities:
        return config.min_embedding_similarity

    top_sim = max(similarities)
    floor_candidates = [
        config.min_embedding_similarity,
        top_sim - config.gap_from_top,
    ]
    if corpus_size >= 8:
        floor_candidates.append(float(np.percentile(similarities, config.keep_percentile)))

    return max(floor_candidates)


@dataclass
class _RelevanceEvaluation:
    passes: bool
    relevance_score: float
    breakdown: dict[str, float]
    filter_reason: str | None


def _evaluate_paper(
    paper: RankedPaper,
    *,
    config: RelevanceScoringConfig,
    concepts: list[str],
    embedding_similarity: float | None,
    embedding_checks_enabled: bool,
    embedding_floor: float,
) -> _RelevanceEvaluation:
    breakdown = dict(paper.score_breakdown)
    reasons: list[str] = []

    rank_ok = paper.rank_score >= config.min_rank_score
    breakdown["relevance_rank_ok"] = 1.0 if rank_ok else 0.0
    if not rank_ok:
        reasons.append(
            f"rank_score {paper.rank_score:.4f} < {config.min_rank_score:.4f}"
        )

    embedding_ok = True
    if embedding_checks_enabled and embedding_similarity is not None:
        embedding_ok = embedding_similarity >= embedding_floor
        breakdown["relevance_embedding_ok"] = 1.0 if embedding_ok else 0.0
        breakdown["adaptive_embedding_floor"] = round(embedding_floor, 4)
        if not embedding_ok:
            reasons.append(
                "embedding_similarity "
                f"{embedding_similarity:.4f} < {embedding_floor:.4f}"
            )
    else:
        breakdown["relevance_embedding_ok"] = 1.0

    concepts_ok = True
    if config.require_all_concepts and len(concepts) >= 2:
        concepts_ok = _concept_groups_match(
            paper.paper,
            concepts,
            mode=config.concept_match_mode,
        )
        breakdown["relevance_concepts_ok"] = 1.0 if concepts_ok else 0.0
        if not concepts_ok:
            reasons.append("missing required concept match")
    else:
        breakdown["relevance_concepts_ok"] = 1.0

    if embedding_similarity is not None:
        breakdown["embedding_similarity"] = round(embedding_similarity, 4)

    relevance_score = _combined_relevance_score(paper.rank_score, embedding_similarity)
    breakdown["relevance_score"] = round(relevance_score, 4)
    breakdown["relevance_pass"] = 1.0 if rank_ok and embedding_ok and concepts_ok else 0.0

    passes = rank_ok and embedding_ok and concepts_ok
    filter_reason = "; ".join(reasons) if reasons else None
    return _RelevanceEvaluation(
        passes=passes,
        relevance_score=relevance_score,
        breakdown=breakdown,
        filter_reason=filter_reason,
    )


def _select_filtered_papers(
    evaluated: list[tuple[RankedPaper, _RelevanceEvaluation]],
    *,
    min_papers: int,
) -> tuple[list[RankedPaper], list[str]]:
    warnings: list[str] = []
    passing = [paper for paper, result in evaluated if result.passes]
    min_keep = min(min_papers, len(evaluated))

    if not passing:
        filtered = [
            paper
            for paper, _ in sorted(
                evaluated,
                key=lambda item: item[1].relevance_score,
                reverse=True,
            )[: max(1, len(evaluated) // 2)]
        ]
        warnings.append(
            "All ranked papers failed relevance checks; keeping top half by combined score"
        )
        return filtered, warnings

    if len(passing) >= min_keep:
        return passing, warnings

    filtered = [
        paper
        for paper, _ in sorted(
            evaluated,
            key=lambda item: item[1].relevance_score,
            reverse=True,
        )[:min_keep]
    ]
    warnings.append(
        f"Raised relevance floor to keep at least {min_keep} paper(s) by combined score"
    )
    return filtered, warnings


class RelevanceScoringStage:
    """Pipeline stage that filters ranked papers below composite relevance thresholds."""

    name = "relevance_scoring"

    async def run(
        self,
        ctx: PipelineContext,
        data: list[RankedPaper],
    ) -> StageResult[list[RankedPaper]]:
        started = time.perf_counter()
        warnings: list[str] = []
        config = ctx.config.relevance_scoring

        ranked, adapter_warnings = ensure_ranked_papers(
            data,
            ctx.query,
            config=ctx.config.ranking,
        )
        warnings.extend(adapter_warnings)

        query_embedding = get_query_embedding(ctx)
        embedding_checks_enabled = query_embedding is not None
        concepts = _core_concepts(ctx.query, ctx)

        paper_similarities: list[tuple[RankedPaper, float | None]] = []
        embedding_similarities: list[float] = []

        for paper in ranked:
            paper_embedding = get_paper_embedding(ctx, paper.paper.paper_id)
            embedding_similarity: float | None = None
            if query_embedding is not None and paper_embedding is not None:
                embedding_similarity = cosine_similarity(query_embedding, paper_embedding)
                embedding_similarities.append(embedding_similarity)
            paper_similarities.append((paper, embedding_similarity))

        embedding_floor = config.min_embedding_similarity
        if (
            embedding_checks_enabled
            and config.adaptive_embedding
            and embedding_similarities
        ):
            embedding_floor = compute_adaptive_embedding_floor(
                embedding_similarities,
                config=config,
                corpus_size=len(ranked),
            )

        evaluated: list[tuple[RankedPaper, _RelevanceEvaluation]] = []
        filter_reasons: dict[str, str] = {}

        for paper, embedding_similarity in paper_similarities:
            result = _evaluate_paper(
                paper,
                config=config,
                concepts=concepts,
                embedding_similarity=embedding_similarity,
                embedding_checks_enabled=embedding_checks_enabled,
                embedding_floor=embedding_floor,
            )
            enriched = paper.model_copy(update={"score_breakdown": result.breakdown})
            evaluated.append((enriched, result))
            if result.filter_reason:
                filter_reasons[enriched.paper.paper_id] = result.filter_reason

        if not evaluated:
            duration_ms = (time.perf_counter() - started) * 1000
            return StageResult(
                output=[],
                duration_ms=duration_ms,
                metrics={"papers_scored": 0, "papers_filtered": 0},
            )

        filtered, selection_warnings = _select_filtered_papers(
            evaluated,
            min_papers=config.min_papers,
        )
        warnings.extend(selection_warnings)

        removed = len(evaluated) - len(filtered)
        if removed:
            warnings.append(f"Filtered {removed} low-relevance paper(s)")

        if filter_reasons:
            ctx.set_artifact("relevance_filter_reasons", filter_reasons)

        duration_ms = (time.perf_counter() - started) * 1000
        ctx.set_artifact("ranked_papers", filtered)

        return StageResult(
            output=filtered,
            duration_ms=duration_ms,
            metrics={
                "papers_scored": len(evaluated),
                "papers_filtered": removed,
                "papers_kept": len(filtered),
                "embedding_checks_enabled": embedding_checks_enabled,
                "adaptive_embedding_enabled": config.adaptive_embedding,
                "adaptive_embedding_floor": (
                    round(embedding_floor, 4)
                    if embedding_checks_enabled and config.adaptive_embedding
                    else None
                ),
                "concept_count": len(concepts),
            },
            warnings=warnings,
        )
