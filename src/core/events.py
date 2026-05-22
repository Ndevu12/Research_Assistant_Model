# -*- coding: utf-8 -*-
"""Pipeline stage lifecycle hooks for observability and future UI integration."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .context import PipelineContext, StageResult

StageCallback = Callable[[str, PipelineContext, Any], Awaitable[None] | None]
StageResultCallback = Callable[[str, PipelineContext, StageResult[Any]], Awaitable[None] | None]


@dataclass
class PipelineEventBus:
    """Lightweight event bus for pipeline stage lifecycle hooks."""

    _on_stage_start: list[StageCallback] = field(default_factory=list)
    _on_stage_complete: list[StageResultCallback] = field(default_factory=list)
    _on_stage_error: list[StageResultCallback] = field(default_factory=list)

    def on_stage_start(self, callback: StageCallback) -> None:
        """Register a callback invoked before a stage runs."""
        self._on_stage_start.append(callback)

    def on_stage_complete(self, callback: StageResultCallback) -> None:
        """Register a callback invoked after a stage completes successfully."""
        self._on_stage_complete.append(callback)

    def on_stage_error(self, callback: StageResultCallback) -> None:
        """Register a callback invoked when a stage returns partial/error results."""
        self._on_stage_error.append(callback)

    async def emit_stage_start(self, stage_name: str, ctx: PipelineContext, data: Any) -> None:
        await self._dispatch(self._on_stage_start, stage_name, ctx, data)

    async def emit_stage_complete(
        self,
        stage_name: str,
        ctx: PipelineContext,
        result: StageResult[Any],
    ) -> None:
        callbacks = self._on_stage_complete if not result.partial else self._on_stage_error
        await self._dispatch_result(callbacks, stage_name, ctx, result)

    async def _dispatch(
        self,
        callbacks: list[StageCallback],
        stage_name: str,
        ctx: PipelineContext,
        data: Any,
    ) -> None:
        for callback in callbacks:
            await self._invoke(callback, stage_name, ctx, data)

    async def _dispatch_result(
        self,
        callbacks: list[StageResultCallback],
        stage_name: str,
        ctx: PipelineContext,
        result: StageResult[Any],
    ) -> None:
        for callback in callbacks:
            await self._invoke(callback, stage_name, ctx, result)

    @staticmethod
    async def _invoke(callback: Callable[..., Any], *args: Any) -> None:
        outcome = callback(*args)
        if asyncio.iscoroutine(outcome):
            await outcome


_default_bus = PipelineEventBus()


def get_event_bus() -> PipelineEventBus:
    """Return the process-wide pipeline event bus."""
    return _default_bus


class StageEventCollector:
    """Collect stage events for tests and diagnostics."""

    def __init__(self) -> None:
        self.started: list[tuple[str, Any]] = []
        self.completed: list[tuple[str, StageResult[Any]]] = []
        self._subscriptions: dict[str, list[Callable[..., Any]]] = defaultdict(list)

    def attach(self, bus: PipelineEventBus | None = None) -> PipelineEventBus:
        target = bus or _default_bus

        async def _on_start(stage_name: str, _ctx: PipelineContext, data: Any) -> None:
            self.started.append((stage_name, data))

        async def _on_complete(
            stage_name: str,
            _ctx: PipelineContext,
            result: StageResult[Any],
        ) -> None:
            self.completed.append((stage_name, result))

        target.on_stage_start(_on_start)
        target.on_stage_complete(_on_complete)
        return target
