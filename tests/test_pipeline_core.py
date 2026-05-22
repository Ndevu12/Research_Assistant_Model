# -*- coding: utf-8 -*-
"""Tests for core pipeline orchestration."""

from __future__ import annotations

from typing import Any

import pytest

from src.config.settings import AppSettings
from src.core.context import PipelineContext, StageResult
from src.core.metrics import PipelineMetrics
from src.core.pipeline import ResearchPipeline


class EchoStage:
    name = "echo"

    async def run(self, ctx: PipelineContext, data: Any) -> StageResult[Any]:
        return StageResult(output=f"echo:{data}", duration_ms=1.0)


class FailingStage:
    name = "failing"

    async def run(self, ctx: PipelineContext, data: Any) -> StageResult[Any]:
        raise RuntimeError("stage failure")


class PartialStage:
    name = "partial"

    async def run(self, ctx: PipelineContext, data: Any) -> StageResult[Any]:
        return StageResult(
            output=data,
            duration_ms=2.0,
            warnings=["partial result"],
            partial=True,
        )


@pytest.mark.asyncio
async def test_pipeline_runs_stages_in_order() -> None:
    pipeline = ResearchPipeline([EchoStage()], AppSettings())
    result = await pipeline.execute("test query")

    assert result.output == "echo:test query"
    assert result.query == "test query"
    assert "echo" in result.stage_results
    assert result.partial is False


@pytest.mark.asyncio
async def test_pipeline_continues_after_stage_failure() -> None:
    config = AppSettings(pipeline={"continue_on_stage_failure": True})
    pipeline = ResearchPipeline([FailingStage(), EchoStage()], config)
    result = await pipeline.execute("query")

    assert result.partial is True
    assert "failing" in result.stage_results
    assert result.stage_results["failing"]["partial"] is True
    assert "echo" in result.stage_results
    assert result.output == "echo:query"


@pytest.mark.asyncio
async def test_pipeline_skips_disabled_stages() -> None:
    config = AppSettings(
        pipeline={
            "enabled_stages": {
                "echo": False,
            }
        }
    )
    pipeline = ResearchPipeline([EchoStage()], config)
    result = await pipeline.execute("query")

    assert result.output == "query"
    assert result.stage_results == {}


@pytest.mark.asyncio
async def test_pipeline_records_partial_stage() -> None:
    pipeline = ResearchPipeline([PartialStage()], AppSettings())
    result = await pipeline.execute("query")

    assert result.partial is True
    assert "partial result" in result.warnings


@pytest.mark.asyncio
async def test_pipeline_isolates_stages_and_preserves_order() -> None:
    """Each mocked stage receives prior output and runs in declared order."""
    call_order: list[str] = []

    class StageA:
        name = "stage_a"

        async def run(self, ctx: PipelineContext, data: Any) -> StageResult[Any]:
            call_order.append(self.name)
            assert data == "isolation query"
            return StageResult(output="a-out", duration_ms=1.0)

    class StageB:
        name = "stage_b"

        async def run(self, ctx: PipelineContext, data: Any) -> StageResult[Any]:
            call_order.append(self.name)
            assert data == "a-out"
            return StageResult(output="b-out", duration_ms=1.0)

    class StageC:
        name = "stage_c"

        async def run(self, ctx: PipelineContext, data: Any) -> StageResult[Any]:
            call_order.append(self.name)
            assert data == "b-out"
            return StageResult(
                output="c-out",
                duration_ms=1.0,
                warnings=["stage c degraded"],
                partial=True,
            )

    pipeline = ResearchPipeline([StageA(), StageB(), StageC()], AppSettings())
    result = await pipeline.execute("isolation query")

    assert call_order == ["stage_a", "stage_b", "stage_c"]
    assert result.output == "c-out"
    assert result.partial is True
    assert "stage c degraded" in result.warnings
    assert set(result.stage_results) == {"stage_a", "stage_b", "stage_c"}


@pytest.mark.asyncio
async def test_pipeline_propagates_partial_from_multiple_stages() -> None:
    class FirstPartial:
        name = "first_partial"

        async def run(self, ctx: PipelineContext, data: Any) -> StageResult[Any]:
            return StageResult(output=data, duration_ms=1.0, partial=True, warnings=["first"])

    class SecondPartial:
        name = "second_partial"

        async def run(self, ctx: PipelineContext, data: Any) -> StageResult[Any]:
            return StageResult(output=data, duration_ms=1.0, partial=True, warnings=["second"])

    pipeline = ResearchPipeline([FirstPartial(), SecondPartial()], AppSettings())
    result = await pipeline.execute("partial query")

    assert result.partial is True
    assert "first" in result.warnings
    assert "second" in result.warnings
    assert result.stage_results["first_partial"]["partial"] is True
    assert result.stage_results["second_partial"]["partial"] is True


def test_pipeline_metrics_emit_and_finalize() -> None:
    metrics = PipelineMetrics()
    metrics.record_stage("retrieval", duration_ms=50.0)
    metrics.record_retrieval(papers_found=12, providers_failed=["semantic_scholar"])
    metrics.record_ranking(top_score=0.91)
    metrics.record_clustering(num_clusters=3)
    metrics.record_llm_usage(tokens_in=100, tokens_out=200, latency_ms=1500.0)
    metrics.finalize(total_duration_ms=2000.0)

    data = metrics.to_dict()
    assert data["retrieval_papers_found"] == 12
    assert data["ranking_top_score"] == 0.91
    assert data["clustering_num_clusters"] == 3
    assert data["pipeline_total_duration_ms"] == 2000.0
