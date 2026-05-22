# -*- coding: utf-8 -*-
"""Post-ranking relevance filtering stage."""

from __future__ import annotations

import time

from ..core.context import PipelineContext, StageResult
from ..core.paper_adapters import ensure_ranked_papers
from ..retrieval.models import RankedPaper

MIN_RELEVANCE_SCORE = 0.05


class RelevanceScoringStage:
    """Pipeline stage that filters ranked papers below a minimum relevance threshold."""

    name = "relevance_scoring"

    async def run(
        self,
        ctx: PipelineContext,
        data: list[RankedPaper],
    ) -> StageResult[list[RankedPaper]]:
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
                metrics={"papers_scored": 0, "papers_filtered": 0},
            )

        filtered = [paper for paper in ranked if paper.rank_score >= MIN_RELEVANCE_SCORE]
        if not filtered:
            filtered = ranked[: max(1, len(ranked) // 2)]
            warnings.append(
                "All ranked papers fell below the relevance threshold; keeping top half"
            )

        removed = len(ranked) - len(filtered)
        if removed:
            warnings.append(f"Filtered {removed} low-relevance paper(s)")

        ctx.set_artifact("ranked_papers", filtered)

        duration_ms = (time.perf_counter() - started) * 1000
        return StageResult(
            output=filtered,
            duration_ms=duration_ms,
            metrics={
                "papers_scored": len(ranked),
                "papers_filtered": removed,
            },
            warnings=warnings,
        )
