# -*- coding: utf-8 -*-
"""Research gap analysis building on cross-paper synthesis."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from ..core.context import PipelineContext, StageResult
from ..models import AgentFactory, AgentRole, ROLE_SYSTEM_PROMPTS
from ..retrieval.models import GapAnalysisResult, PaperCluster, SynthesisResult
from ..utils.enhanced_response_handler import EnhancedResponseHandler
from ..utils.response_models import RequestContext, ResponseHandlerConfig

if TYPE_CHECKING:
    from ..config.settings import LLMConfig


GAP_ANALYSIS_SYSTEM_PROMPT = ROLE_SYSTEM_PROMPTS[AgentRole.GAP_ANALYSIS]


def resolve_synthesis_input(data: object, ctx: PipelineContext) -> SynthesisResult:
    """Resolve synthesis output even when an upstream stage passed the wrong type."""
    from .synthesis import resolve_synthesis_input as _resolve

    return _resolve(data, ctx)


def recover_gap_analysis_output(ctx: PipelineContext, data: object) -> GapAnalysisResult:
    """Build heuristic gap analysis when the stage fails or receives bad input."""
    existing = ctx.get_artifact("gap_analysis")
    if isinstance(existing, GapAnalysisResult):
        return existing

    clusters: list[PaperCluster] = ctx.get_artifact("paper_clusters") or []
    if isinstance(data, list) and data and isinstance(data[0], PaperCluster):
        clusters = data

    synthesis = resolve_synthesis_input(data, ctx)
    return _heuristic_gap_analysis(synthesis, ctx.query, clusters)


def _heuristic_gap_analysis(
    synthesis: SynthesisResult,
    query: str,
    clusters: list[PaperCluster],
) -> GapAnalysisResult:
    """Derive gap analysis from synthesis fields without an LLM."""
    gaps = list(dict.fromkeys(synthesis.gaps))
    opportunities: list[str] = []

    for disagreement in synthesis.disagreements:
        opportunities.append(f"Resolve disagreement: {disagreement}")

    for gap in gaps:
        opportunities.append(f"Investigate further: {gap}")

    if synthesis.trends:
        opportunities.append(f"Extend emerging trend: {synthesis.trends[0]}")

    underexplored = [
        f"Cluster '{cluster.theme}' has limited coverage ({len(cluster.paper_ids)} paper(s))"
        for cluster in clusters
        if len(cluster.paper_ids) == 1
    ]

    if not gaps:
        gaps = [f"Insufficient evidence to characterize gaps for: {query}"]

    if not opportunities:
        opportunities = [f"Broaden evaluation across methodologies for: {query}"]

    return GapAnalysisResult(
        gaps=gaps,
        opportunities=opportunities[:10],
        underexplored_areas=underexplored[:5],
    )


def _build_gap_prompt(
    query: str,
    synthesis: SynthesisResult,
    clusters: list[PaperCluster],
) -> str:
    cluster_payload = [
        {"theme": cluster.theme, "summary": cluster.summary, "paper_ids": cluster.paper_ids}
        for cluster in clusters
    ]
    return (
        f"Research query: {query}\n\n"
        f"Synthesis output:\n{json.dumps(synthesis.model_dump(), ensure_ascii=False)}\n\n"
        f"Thematic clusters:\n{json.dumps(cluster_payload, ensure_ascii=False)}\n\n"
        "Identify prioritized research gaps, actionable opportunities, and underexplored areas."
    )


async def analyze_gaps(
    query: str,
    synthesis: SynthesisResult,
    clusters: list[PaperCluster] | None = None,
    *,
    llm_config: LLMConfig | None = None,
    handler: EnhancedResponseHandler | None = None,
    session_id: str = "",
) -> GapAnalysisResult:
    """Refine synthesis gaps into prioritized research opportunities."""
    clusters = clusters or []

    if llm_config is None:
        from ..config.settings import get_settings

        llm_config = get_settings().llm

    agent = AgentFactory(llm_config).create_agent(AgentRole.GAP_ANALYSIS, config=llm_config)
    response_handler = handler or EnhancedResponseHandler(ResponseHandlerConfig())
    context = RequestContext(
        user_query=query,
        model_name=llm_config.model,
        session_id=session_id,
    )
    prompt = _build_gap_prompt(query, synthesis, clusters)

    from ..utils.progress_reporter import get_progress_reporter

    reporter = get_progress_reporter()
    if reporter is not None:
        reporter.set_activity("Analyzing research gaps with AI…")

    result = await response_handler.process_structured_response(
        agent,
        prompt,
        context,
        GapAnalysisResult,
        schema_description=(
            '{"gaps": ["..."], "opportunities": ["..."], "underexplored_areas": ["..."]}'
        ),
    )
    if result.success and isinstance(result.data, GapAnalysisResult):
        return result.data
    return _heuristic_gap_analysis(synthesis, query, clusters)


class GapAnalysisStage:
    """Pipeline stage that expands synthesis gaps into research opportunities."""

    name = "gap_analysis"

    def __init__(self, handler: EnhancedResponseHandler | None = None) -> None:
        self.handler = handler

    async def run(
        self,
        ctx: PipelineContext,
        data: SynthesisResult,
    ) -> StageResult[GapAnalysisResult]:
        started = time.perf_counter()
        warnings: list[str] = []
        partial = False

        synthesis = resolve_synthesis_input(data, ctx)
        clusters: list[PaperCluster] = ctx.get_artifact("paper_clusters") or []
        if isinstance(data, list) and data and isinstance(data[0], PaperCluster):
            warnings.append("Gap analysis received cluster data instead of synthesis; using recovered synthesis")
            partial = True

        if not ctx.config.synthesis.llm_enabled:
            gap_result = _heuristic_gap_analysis(synthesis, ctx.query, clusters)
            ctx.set_artifact("gap_analysis", gap_result)
            duration_ms = (time.perf_counter() - started) * 1000
            return StageResult(
                output=gap_result,
                duration_ms=duration_ms,
                metrics={
                    "gap_count": len(gap_result.gaps),
                    "opportunity_count": len(gap_result.opportunities),
                },
                warnings=[*warnings, "Skipped LLM gap analysis (synthesis.llm_enabled=false)"],
                partial=partial,
            )

        try:
            gap_result = await analyze_gaps(
                ctx.query,
                synthesis,
                clusters,
                llm_config=ctx.config.llm,
                handler=self.handler,
                session_id=ctx.session.id,
            )
        except Exception as exc:
            warnings.append(f"Gap analysis failed, using heuristic fallback: {exc}")
            partial = True
            gap_result = _heuristic_gap_analysis(synthesis, ctx.query, clusters)

        ctx.set_artifact("gap_analysis", gap_result)

        duration_ms = (time.perf_counter() - started) * 1000
        return StageResult(
            output=gap_result,
            duration_ms=duration_ms,
            metrics={
                "gap_count": len(gap_result.gaps),
                "opportunity_count": len(gap_result.opportunities),
            },
            warnings=warnings,
            partial=partial,
        )
