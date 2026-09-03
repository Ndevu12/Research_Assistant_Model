# -*- coding: utf-8 -*-
"""Iterative coverage-driven retrieval refinement.

After relevance filtering, the loop asks whether the kept papers actually
answer the query. When coverage is thin it generates targeted follow-up
queries, retrieves for them, and merges the new candidates through the
same deduplication, ranking, and relevance machinery — repeating up to a
configured budget. This turns the one-shot pipeline into the
assess-refine-stop cycle deep-research agents use.

Coverage assessment is LLM-backed (structured output) when synthesis LLM
mode is on, with a concept-coverage heuristic otherwise, so the loop
functions in fully local heuristic runs too.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field

from ..core.context import PipelineContext, StageResult
from ..models.base import AgentRole
from ..retrieval.models import ExpandedQuerySet, RankedPaper
from ..utils.logging_system import logger
from .ranking import rank_papers
from .text_utils import extract_core_concepts, term_matches_text

COVERAGE_ARTIFACT = "coverage_assessment"


class CoverageAssessment(BaseModel):
    """Structured verdict on whether retrieved papers answer the query."""

    sufficient: bool = True
    missing_aspects: list[str] = Field(default_factory=list)
    follow_up_queries: list[str] = Field(default_factory=list)


def heuristic_coverage(
    query: str,
    ranked_papers: list[RankedPaper],
    *,
    min_sufficient_papers: int,
) -> CoverageAssessment:
    """Concept-coverage heuristic: every core concept needs a matching paper."""
    concepts = extract_core_concepts(query)
    texts = [
        f"{item.paper.title} {item.paper.abstract or ''}".lower()
        for item in ranked_papers
    ]

    missing = [
        concept
        for concept in concepts
        if not any(term_matches_text(concept.lower(), text) for text in texts)
    ]

    covered_terms = [c for c in concepts if c not in missing]
    follow_ups = [
        " ".join([concept, *covered_terms[:2]]).strip() for concept in missing
    ]

    sufficient = len(ranked_papers) >= min_sufficient_papers and not missing
    return CoverageAssessment(
        sufficient=sufficient,
        missing_aspects=missing,
        follow_up_queries=follow_ups,
    )


def _coverage_prompt(query: str, ranked_papers: list[RankedPaper]) -> str:
    lines = [f"Research query: {query}", "", "Papers found so far:"]
    for item in ranked_papers[:15]:
        abstract = (item.paper.abstract or "")[:200]
        lines.append(f"- {item.paper.title} ({item.paper.year or 'n.d.'}): {abstract}")
    lines.append("")
    lines.append(
        "Is this set sufficient to answer the query? If not, list the missing "
        "aspects and propose follow-up search queries."
    )
    return "\n".join(lines)


async def assess_coverage(
    query: str,
    ranked_papers: list[RankedPaper],
    ctx: PipelineContext,
) -> CoverageAssessment:
    """LLM coverage assessment with heuristic fallback."""
    config = ctx.config.research_loop
    heuristic = heuristic_coverage(
        query,
        ranked_papers,
        min_sufficient_papers=config.min_sufficient_papers,
    )

    if not ctx.config.synthesis.llm_enabled:
        return heuristic

    from ..models.structured import try_run_structured

    assessment = await try_run_structured(
        AgentRole.COVERAGE,
        _coverage_prompt(query, ranked_papers),
        CoverageAssessment,
        ctx.config.llm,
    )
    return assessment if assessment is not None else heuristic


class ResearchLoopStage:
    """Pipeline stage that refines retrieval until coverage is sufficient."""

    name = "research_loop"

    async def run(
        self,
        ctx: PipelineContext,
        data: list[RankedPaper],
    ) -> StageResult[list[RankedPaper]]:
        started = time.perf_counter()
        config = ctx.config.research_loop
        warnings: list[str] = []
        iterations = 0
        follow_ups_used: list[str] = []
        papers = data

        def _result(assessment: CoverageAssessment | None) -> StageResult[list[RankedPaper]]:
            if assessment is not None:
                ctx.set_artifact(COVERAGE_ARTIFACT, assessment.model_dump())
            return StageResult(
                output=papers,
                duration_ms=(time.perf_counter() - started) * 1000,
                metrics={
                    "iterations_run": iterations,
                    "follow_up_queries": follow_ups_used,
                    "papers_after_loop": len(papers),
                    "coverage_sufficient": bool(assessment.sufficient)
                    if assessment
                    else None,
                },
                warnings=warnings,
            )

        if not config.enabled or not papers:
            return _result(None)

        assessment = await assess_coverage(ctx.query, papers, ctx)

        while (
            not assessment.sufficient
            and assessment.follow_up_queries
            and iterations < config.max_iterations
        ):
            iterations += 1
            follow_ups = [
                q.strip()
                for q in assessment.follow_up_queries[: config.max_follow_up_queries]
                if q.strip()
            ]
            if not follow_ups:
                break
            follow_ups_used.extend(follow_ups)
            logger.info(
                "Research loop iteration %d: retrieving %d follow-up quer(ies)",
                iterations,
                len(follow_ups),
            )

            try:
                papers = await self._refine(ctx, papers, follow_ups)
            except Exception as exc:
                warnings.append(f"Research loop retrieval failed: {exc}")
                break

            assessment = await assess_coverage(ctx.query, papers, ctx)

        ctx.set_artifact("ranked_papers", papers)
        return _result(assessment)

    async def _refine(
        self,
        ctx: PipelineContext,
        current: list[RankedPaper],
        follow_ups: list[str],
    ) -> list[RankedPaper]:
        """Retrieve follow-up queries and re-run dedup, ranking, and filtering."""
        from ..embeddings import try_create_embedding_provider
        from ..retrieval.deduplication import deduplicate_papers
        from ..retrieval.retrieval_stage import retrieve_papers
        from .embedding_context import store_ranking_embedding_result
        from .relevance_scoring import RelevanceScoringStage

        expanded = ExpandedQuerySet(original=follow_ups[0], variants=follow_ups[1:])
        new_papers, warnings, _failed = await retrieve_papers(expanded, ctx.config)
        if not new_papers:
            return current

        embedder = try_create_embedding_provider(ctx.config.embedding)
        base = [item.paper for item in current]
        try:
            combined, _stats = deduplicate_papers(
                base + new_papers,
                config=ctx.config.deduplication,
                embedder=embedder,
            )
            ranking_result = rank_papers(
                combined, ctx.query, config=ctx.config.ranking, embedder=embedder
            )
        except ImportError:
            combined, _stats = deduplicate_papers(
                base + new_papers,
                config=ctx.config.deduplication.model_copy(
                    update={"enable_embedding_dedup": False}
                ),
                embedder=None,
            )
            ranking_result = rank_papers(
                combined, ctx.query, config=ctx.config.ranking, embedder=None
            )

        store_ranking_embedding_result(
            ctx,
            ranking_result.query_embedding,
            ranking_result.paper_embeddings,
        )

        filtered = await RelevanceScoringStage().run(ctx, ranking_result.ranked)
        return filtered.output
