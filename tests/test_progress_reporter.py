# -*- coding: utf-8 -*-
"""Tests for live CLI progress reporting."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.context import PipelineContext, ResearchSession, StageResult
from src.core.events import PipelineEventBus
from src.utils.progress_reporter import (
    PipelineProgressReporter,
    get_progress_reporter,
    reset_progress_reporter,
    set_progress_reporter,
    stage_label,
    stream_agent_text,
)


class TestStageLabels:
    def test_known_stage_has_friendly_label(self) -> None:
        assert stage_label("synthesis") == "Synthesizing cross-paper insights"

    def test_unknown_stage_is_title_cased(self) -> None:
        assert stage_label("custom_stage") == "Custom Stage"


class TestProgressReporter:
    @pytest.mark.asyncio
    async def test_disabled_reporter_uses_blocking_agent_run(self) -> None:
        reporter = PipelineProgressReporter(enabled=False)
        agent = MagicMock()
        agent.run = AsyncMock(return_value=MagicMock(output='{"ok": true}'))

        text = await reporter.stream_agent_response(agent, "prompt", label="Testing")

        assert text == '{"ok": true}'
        agent.run.assert_awaited_once_with("prompt")

    @pytest.mark.asyncio
    async def test_stream_agent_text_without_reporter(self) -> None:
        agent = MagicMock()
        agent.run = AsyncMock(return_value=MagicMock(output="hello"))

        text = await stream_agent_text(agent, "prompt", label="Testing")

        assert text == "hello"

    @pytest.mark.asyncio
    async def test_stage_events_update_completed_list(self) -> None:
        reporter = PipelineProgressReporter(enabled=False)
        bus = PipelineEventBus()
        reporter.attach(bus)
        ctx = PipelineContext.create(
            query="test",
            config=MagicMock(),
            session=ResearchSession(),
        )

        await bus.emit_stage_start("ranking", ctx, "data")
        await bus.emit_stage_complete(
            "ranking",
            ctx,
            StageResult(output="ranked", duration_ms=42.0),
        )

        assert len(reporter._completed) == 1
        assert reporter._completed[0][0] == "ranking"

    @pytest.mark.asyncio
    async def test_context_var_round_trip(self) -> None:
        reporter = PipelineProgressReporter(enabled=False)
        token = set_progress_reporter(reporter)
        try:
            assert get_progress_reporter() is reporter
        finally:
            reset_progress_reporter(token)
        assert get_progress_reporter() is None

    def test_non_tty_disables_reporter(self) -> None:
        with patch("src.utils.progress_reporter.sys.stderr") as mock_stderr:
            mock_stderr.isatty.return_value = False
            reporter = PipelineProgressReporter(enabled=True)
            assert reporter.enabled is False
