# -*- coding: utf-8 -*-
"""Shared helpers for pipeline-backed orchestrator tests."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from unittest.mock import AsyncMock, patch

from src.core.pipeline import ResearchPipelineResult
from src.retrieval.models import EnhancedResearchReport, PaperAnalysis, PaperCluster, SynthesisResult


def build_report_from_json_payload(payload: dict) -> EnhancedResearchReport:
    """Convert legacy JSON payload shapes into an enhanced report."""
    papers = [
        PaperAnalysis(
            title=paper.get("title", ""),
            year=paper.get("year"),
            venue=paper.get("venue"),
            url=paper.get("url"),
            doi=paper.get("doi"),
            key_points=paper.get("key_points", []),
            why_relevant=paper.get("why_relevant", []),
        )
        for paper in payload.get("papers", [])
    ]
    return EnhancedResearchReport(
        query=payload.get("query", ""),
        executive_summary=f"Research overview for: {payload.get('query', '')}",
        papers=papers,
        clusters=[
            PaperCluster(
                theme="Retrieved Literature",
                summary="Papers relevant to the query.",
                paper_ids=[paper.paper_id or paper.title for paper in papers if paper.title],
            )
        ] if papers else [],
        synthesis=SynthesisResult(
            agreements=[paper.key_points[0] for paper in papers if paper.key_points][:3],
            datasets=[],
            methodologies=[],
        ),
    )


@contextmanager
def mock_pipeline_result(
    report: EnhancedResearchReport,
    *,
    partial: bool = False,
    warnings: list[str] | None = None,
) -> Iterator[None]:
    """Patch orchestrator pipeline execution with a canned report."""
    pipeline_result = ResearchPipelineResult(
        query=report.query,
        output=report,
        session_id="test-session",
        partial=partial,
        warnings=warnings or [],
    )
    with patch(
        "src.retrieval.orchestrator.run_research_with_result",
        new=AsyncMock(return_value=(report, pipeline_result)),
    ):
        yield


@contextmanager
def mock_pipeline_exception(message: str) -> Iterator[None]:
    """Patch orchestrator pipeline execution to raise an exception."""
    with patch(
        "src.retrieval.orchestrator.run_research_with_result",
        new=AsyncMock(side_effect=Exception(message)),
    ):
        yield
