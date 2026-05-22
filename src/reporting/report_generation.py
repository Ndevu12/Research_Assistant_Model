# -*- coding: utf-8 -*-
"""Report assembly stage for the research pipeline."""

from __future__ import annotations

import time

from ..core.context import PipelineContext, StageResult
from ..retrieval.models import (
    EnhancedResearchReport,
    GapAnalysisResult,
    PaperAnalysis,
    PaperCluster,
    RankedPaper,
    SynthesisResult,
)


def _build_executive_summary(
    query: str,
    synthesis: SynthesisResult | None,
    clusters: list[PaperCluster],
    paper_count: int,
) -> str:
    parts: list[str] = []

    if synthesis and synthesis.agreements:
        parts.append(synthesis.agreements[0])

    if clusters:
        themes = ", ".join(cluster.theme for cluster in clusters[:3])
        parts.append(
            f"Analysis of {paper_count} paper(s) grouped into "
            f"{len(clusters)} theme(s): {themes}."
        )
    elif paper_count:
        parts.append(f"Review of {paper_count} retrieved paper(s) for: {query}.")
    else:
        parts.append(f"No papers were retrieved for: {query}.")

    if synthesis and synthesis.trends:
        parts.append(synthesis.trends[0])

    return " ".join(parts)


def _build_timeline(
    ranked_papers: list[RankedPaper],
    synthesis: SynthesisResult | None,
) -> list[str]:
    timeline: list[str] = []
    years = sorted({paper.paper.year for paper in ranked_papers if paper.paper.year})

    for year in years:
        count = sum(1 for paper in ranked_papers if paper.paper.year == year)
        timeline.append(f"{year}: {count} paper(s)")

    if synthesis:
        timeline.extend(synthesis.trends)

    return list(dict.fromkeys(timeline))


def assemble_report(ctx: PipelineContext, exports: dict[str, str]) -> EnhancedResearchReport:
    """Build an enhanced report from pipeline context artifacts."""
    synthesis: SynthesisResult | None = ctx.get_artifact("synthesis_result")
    gap_result: GapAnalysisResult | None = ctx.get_artifact("gap_analysis")
    clusters: list[PaperCluster] = ctx.get_artifact("paper_clusters") or []
    analyses: list[PaperAnalysis] = ctx.get_artifact("paper_analyses") or []
    ranked_papers: list[RankedPaper] = ctx.get_artifact("ranked_papers") or []
    citation_index: dict[str, str] = ctx.get_artifact("citation_index") or {}

    gaps: list[str] = []
    if gap_result:
        gaps.extend(gap_result.gaps)
    elif synthesis:
        gaps.extend(synthesis.gaps)

    report = EnhancedResearchReport(
        query=ctx.query,
        executive_summary=_build_executive_summary(
            ctx.query,
            synthesis,
            clusters,
            len(analyses),
        ),
        papers=analyses,
        clusters=clusters,
        synthesis=synthesis,
        gap_analysis=gap_result,
        gaps=list(dict.fromkeys(gaps)),
        timeline=_build_timeline(ranked_papers, synthesis),
        citation_index=citation_index,
        exports=exports,
    )
    return report


class ReportGenerationStage:
    """Pipeline stage that assembles the final enhanced research report."""

    name = "report_generation"

    async def run(
        self,
        ctx: PipelineContext,
        data: dict[str, str],
    ) -> StageResult[EnhancedResearchReport]:
        started = time.perf_counter()
        report = assemble_report(ctx, data)
        ctx.set_artifact("enhanced_report", report)

        duration_ms = (time.perf_counter() - started) * 1000
        return StageResult(
            output=report,
            duration_ms=duration_ms,
            metrics={
                "paper_count": len(report.papers),
                "cluster_count": len(report.clusters),
            },
        )
