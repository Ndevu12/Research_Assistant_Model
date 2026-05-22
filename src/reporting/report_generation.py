# -*- coding: utf-8 -*-
"""Report assembly stage for the research pipeline."""

from __future__ import annotations

import time

from ..analysis.synthesis import embedding_similarity_for_paper, sentence_aligns_with_query
from ..config.settings import RelevanceScoringConfig
from ..core.context import PipelineContext, StageResult
from ..research.query_expansion import extract_core_concepts
from ..research.relevance_scoring import compute_adaptive_embedding_floor
from ..retrieval.models import (
    EnhancedResearchReport,
    GapAnalysisResult,
    PaperAnalysis,
    PaperCluster,
    RankedPaper,
    SynthesisResult,
)


def _cluster_theme_list(clusters: list[PaperCluster]) -> str:
    themes = [cluster.theme for cluster in clusters if cluster.theme]
    if not themes:
        return "general topics"
    return ", ".join(themes[:5])


def _top_centroid_themes(clusters: list[PaperCluster]) -> str:
    themes = [cluster.theme for cluster in clusters[:3] if cluster.theme]
    if not themes:
        return "core research themes"
    return ", ".join(themes)


def _embedding_similarities(ranked_papers: list[RankedPaper]) -> list[float]:
    return [
        float(paper.score_breakdown["embedding_similarity"])
        for paper in ranked_papers
        if "embedding_similarity" in paper.score_breakdown
    ]


def _summary_embedding_floor(
    ranked_papers: list[RankedPaper],
    config: RelevanceScoringConfig,
) -> float:
    similarities = _embedding_similarities(ranked_papers)
    if not similarities or not config.adaptive_embedding:
        return config.min_embedding_similarity
    return compute_adaptive_embedding_floor(
        similarities,
        config=config,
        corpus_size=len(ranked_papers),
    )


def _validated_finding_snippet(
    synthesis: SynthesisResult | None,
    query: str,
    ranked_papers: list[RankedPaper],
    embedding_floor: float,
) -> str | None:
    if not ranked_papers or not synthesis or not synthesis.agreements:
        return None

    top_similarity = max(embedding_similarity_for_paper(paper) for paper in ranked_papers)
    if top_similarity < embedding_floor:
        return None

    concepts = extract_core_concepts(query)
    for agreement in synthesis.agreements:
        if sentence_aligns_with_query(agreement, concepts):
            return agreement
    return None


def _build_executive_summary(
    query: str,
    synthesis: SynthesisResult | None,
    clusters: list[PaperCluster],
    paper_count: int,
    ranked_papers: list[RankedPaper] | None = None,
    relevance_config: RelevanceScoringConfig | None = None,
) -> str:
    if paper_count == 0:
        return f"No papers were retrieved for: {query}."

    cluster_themes = _cluster_theme_list(clusters)
    focus_themes = _top_centroid_themes(clusters)
    summary = (
        f"{query}: review of {paper_count} paper(s) across themes "
        f"{cluster_themes}. Key focus areas include {focus_themes}."
    )

    config = relevance_config or RelevanceScoringConfig()
    embedding_floor = _summary_embedding_floor(ranked_papers or [], config)
    snippet = _validated_finding_snippet(
        synthesis,
        query,
        ranked_papers or [],
        embedding_floor,
    )
    if snippet:
        summary = f"{summary} Notable finding: {snippet}"

    return summary


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
            ranked_papers=ranked_papers,
            relevance_config=ctx.config.relevance_scoring,
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
