# -*- coding: utf-8 -*-
"""Composable research pipeline orchestration."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from ..config.resolve_llm_features import resolve_effective_settings
from ..config.settings import AppSettings
from ..utils.logging_system import logger
from .context import PipelineContext, ResearchSession, StageResult
from .events import PipelineEventBus, get_event_bus
from .stage_recovery import recover_stage_output


@runtime_checkable
class PipelineStage(Protocol):
    """Protocol for a single pipeline stage."""

    name: str

    async def run(self, ctx: PipelineContext, data: Any) -> StageResult[Any]:
        """Execute the stage and return a typed result."""
        ...


class ResearchPipelineResult(BaseModel):
    """Final output of a pipeline run."""

    query: str
    output: Any = None
    session_id: str
    stage_results: dict[str, dict[str, Any]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    partial: bool = False
    duration_ms: float = 0.0
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResearchPipeline:
    """Runs an ordered list of pipeline stages with graceful degradation."""

    def __init__(
        self,
        stages: list[PipelineStage],
        config: AppSettings,
        event_bus: PipelineEventBus | None = None,
    ) -> None:
        self.stages = stages
        self.config = config
        self.event_bus = event_bus or get_event_bus()

    def _is_stage_enabled(self, stage_name: str) -> bool:
        enabled = self.config.pipeline.enabled_stages.get(stage_name, True)
        return enabled

    def _stage_timeout_seconds(self, stage_name: str) -> int:
        if stage_name == "synthesis":
            return self.config.pipeline.synthesis_timeout_seconds
        return self.config.pipeline.stage_timeout_seconds

    async def _run_stage(
        self,
        stage: PipelineStage,
        ctx: PipelineContext,
        data: Any,
    ) -> StageResult[Any]:
        timeout = self._stage_timeout_seconds(stage.name)
        started = time.perf_counter()

        try:
            if timeout > 0:
                result = await asyncio.wait_for(stage.run(ctx, data), timeout=timeout)
            else:
                result = await stage.run(ctx, data)
        except asyncio.TimeoutError:
            duration_ms = (time.perf_counter() - started) * 1000
            message = f"Stage '{stage.name}' timed out after {timeout}s"
            logger.warning(message)
            recovered_output = recover_stage_output(stage.name, ctx, data)
            return StageResult(
                output=recovered_output,
                duration_ms=duration_ms,
                warnings=[message, f"Recovered {stage.name} output via heuristic fallback"],
                partial=True,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            message = f"Stage '{stage.name}' failed: {exc}"
            logger.error(message, exc_info=True)
            if self.config.pipeline.continue_on_stage_failure:
                recovered_output = recover_stage_output(stage.name, ctx, data)
                return StageResult(
                    output=recovered_output,
                    duration_ms=duration_ms,
                    warnings=[message],
                    partial=True,
                )
            raise exc

        if result.duration_ms <= 0:
            result.duration_ms = (time.perf_counter() - started) * 1000
        return result

    def _write_debug_dump(self, ctx: PipelineContext) -> None:
        debug_dir = Path("logs") / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dump_path = debug_dir / f"pipeline_{ctx.session.id}_{timestamp}.json"
        with dump_path.open("w", encoding="utf-8") as handle:
            json.dump(ctx.to_debug_dict(), handle, indent=2, default=str)
        logger.debug("Wrote pipeline debug dump to %s", dump_path)

    async def execute(
        self,
        query: str,
        session: ResearchSession | None = None,
        initial_artifacts: dict[str, Any] | None = None,
    ) -> ResearchPipelineResult:
        """Run all enabled stages sequentially."""
        effective_config = resolve_effective_settings(self.config)
        ctx = PipelineContext.create(query=query, config=effective_config, session=session)
        if initial_artifacts:
            for key, value in initial_artifacts.items():
                ctx.set_artifact(key, value)
        data: Any = query
        started = time.perf_counter()

        for stage in self.stages:
            if not self._is_stage_enabled(stage.name):
                logger.debug("Skipping disabled stage: %s", stage.name)
                continue

            logger.info("Running pipeline stage: %s", stage.name)
            await self.event_bus.emit_stage_start(stage.name, ctx, data)
            result = await self._run_stage(stage, ctx, data)
            await self.event_bus.emit_stage_complete(stage.name, ctx, result)
            ctx.record_stage_result(stage.name, result)
            data = result.output

        total_duration_ms = (time.perf_counter() - started) * 1000
        ctx.metrics.finalize(total_duration_ms)
        ctx.metrics.emit_to_logger(logger)

        if self.config.debug_enabled:
            self._write_debug_dump(ctx)

        stage_summaries = {
            name: {
                "duration_ms": result.duration_ms,
                "partial": result.partial,
                "warnings": result.warnings,
                "metrics": result.metrics,
            }
            for name, result in ctx.stage_results.items()
        }

        artifact_keys = (
            "expanded_queries",
            "ranked_papers",
            "retrieved_papers",
            "paper_analyses",
            "paper_clusters",
            "synthesis_result",
            "gap_analysis",
            "citation_exports",
            "citation_index",
            "enhanced_report",
        )
        artifacts = {
            key: ctx.get_artifact(key)
            for key in artifact_keys
            if ctx.get_artifact(key) is not None
        }

        return ResearchPipelineResult(
            query=query,
            output=data,
            session_id=ctx.session.id,
            stage_results=stage_summaries,
            warnings=list(ctx.warnings),
            partial=ctx.is_partial,
            duration_ms=total_duration_ms,
            metrics=ctx.metrics.to_dict(),
            artifacts=artifacts,
        )
