# -*- coding: utf-8 -*-
"""Claim verification against paper sources before report generation.

Each paper's key points are checked against that paper's own sources —
abstract plus any grounded full-text passages. Unsupported claims are
flagged in the report rather than presented as fact, and the report
carries an aggregate verification summary.

Verification is LLM-backed (structured output) when synthesis LLM mode is
on, with a term-coverage heuristic otherwise. Flagging is deliberately
conservative: a claim is marked unverified only when its content terms
are largely absent from the paper's sources.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field

from ..core.context import PipelineContext, StageResult
from ..models.base import AgentRole
from ..research.text_utils import extract_query_terms, term_matches_text
from ..retrieval.models import (
    GapAnalysisResult,
    PaperAnalysis,
    RankedPaper,
    VerificationSummary,
)

VERIFICATION_ARTIFACT = "verification_summary"


class _ClaimVerdicts(BaseModel):
    """Structured output: which numbered claims lack support in the sources."""

    unsupported_claim_numbers: list[int] = Field(default_factory=list)


def _paper_sources(
    analysis: PaperAnalysis,
    abstracts: dict[str, str],
    passages: dict[str, list[str]],
) -> str:
    parts: list[str] = []
    if analysis.paper_id:
        if analysis.paper_id in abstracts:
            parts.append(abstracts[analysis.paper_id])
        parts.extend(passages.get(analysis.paper_id, []))
    return "\n".join(parts).lower()


def heuristic_unsupported(
    claims: list[str],
    sources: str,
    *,
    min_term_coverage: float,
) -> list[str]:
    """Claims whose content terms are largely absent from the sources."""
    if not sources:
        return []

    unsupported: list[str] = []
    for claim in claims:
        terms = extract_query_terms(claim)
        if not terms:
            continue
        matched = sum(1 for term in terms if term_matches_text(term, sources))
        if matched / len(terms) < min_term_coverage:
            unsupported.append(claim)
    return unsupported


def _verification_prompt(analysis: PaperAnalysis, sources: str) -> str:
    numbered = "\n".join(
        f"{index}. {claim}" for index, claim in enumerate(analysis.key_points, start=1)
    )
    return (
        f"Paper: {analysis.title}\n\n"
        f"Source material (abstract and full-text passages):\n{sources[:4000]}\n\n"
        f"Claims made about this paper:\n{numbered}\n\n"
        "Which claim numbers are NOT supported by the source material?"
    )


async def _llm_unsupported(
    analysis: PaperAnalysis,
    sources: str,
    ctx: PipelineContext,
) -> list[str] | None:
    from ..models.structured import try_run_structured

    verdicts = await try_run_structured(
        AgentRole.VERIFICATION,
        _verification_prompt(analysis, sources),
        _ClaimVerdicts,
        ctx.config.llm,
    )
    if verdicts is None:
        return None
    return [
        analysis.key_points[number - 1]
        for number in verdicts.unsupported_claim_numbers
        if 1 <= number <= len(analysis.key_points)
    ]


class VerificationStage:
    """Pipeline stage that flags unsupported claims before reporting."""

    name = "verification"

    async def run(
        self,
        ctx: PipelineContext,
        data: GapAnalysisResult,
    ) -> StageResult[GapAnalysisResult]:
        started = time.perf_counter()
        config = ctx.config.verification

        def _result(summary: VerificationSummary | None) -> StageResult[GapAnalysisResult]:
            metrics: dict[str, object] = {}
            if summary is not None:
                ctx.set_artifact(VERIFICATION_ARTIFACT, summary.model_dump())
                metrics = {
                    "claims_checked": summary.claims_checked,
                    "claims_unverified": summary.claims_unverified,
                    "method": summary.method,
                }
            return StageResult(
                output=data,
                duration_ms=(time.perf_counter() - started) * 1000,
                metrics=metrics,
            )

        analyses: list[PaperAnalysis] = ctx.get_artifact("paper_analyses") or []
        if not config.enabled or not analyses:
            return _result(None)

        ranked: list[RankedPaper] = ctx.get_artifact("ranked_papers") or []
        abstracts = {
            item.paper.paper_id: item.paper.abstract or "" for item in ranked
        }
        passages: dict[str, list[str]] = ctx.get_artifact("fulltext_passages") or {}

        use_llm = ctx.config.synthesis.llm_enabled
        method = "llm" if use_llm else "heuristic"

        checked = 0
        unverified_total = 0
        verified_analyses: list[PaperAnalysis] = []

        for analysis in analyses:
            sources = _paper_sources(analysis, abstracts, passages)
            claims = analysis.key_points
            checked += len(claims)

            unsupported: list[str] | None = None
            if use_llm and claims and sources:
                unsupported = await _llm_unsupported(analysis, sources, ctx)
            if unsupported is None:
                method = "heuristic" if not use_llm else method
                unsupported = heuristic_unsupported(
                    claims,
                    sources,
                    min_term_coverage=config.min_term_coverage,
                )

            unverified_total += len(unsupported)
            verified_analyses.append(
                analysis.model_copy(update={"unverified_points": unsupported})
                if unsupported
                else analysis
            )

        ctx.set_artifact("paper_analyses", verified_analyses)
        summary = VerificationSummary(
            claims_checked=checked,
            claims_unverified=unverified_total,
            method=method,
        )
        return _result(summary)
