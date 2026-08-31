# -*- coding: utf-8 -*-
"""Live CLI progress for pipeline stages and LLM streaming (stderr, TTY-aware)."""

from __future__ import annotations

import sys
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from ..core.context import PipelineContext, StageResult
    from ..core.events import PipelineEventBus

_progress_reporter: ContextVar[PipelineProgressReporter | None] = ContextVar(
    "progress_reporter",
    default=None,
)

STAGE_LABELS: dict[str, str] = {
    "query_understanding": "Understanding your question",
    "query_expansion": "Expanding search queries",
    "retrieval": "Retrieving papers from scholarly APIs",
    "deduplication": "Removing duplicate papers",
    "ranking": "Ranking papers by relevance",
    "snowball": "Following citation trails",
    "relevance_scoring": "Scoring semantic relevance",
    "clustering": "Grouping papers by theme",
    "synthesis": "Synthesizing cross-paper insights",
    "gap_analysis": "Identifying research gaps",
    "citation_export": "Formatting citations",
    "report_generation": "Organizing final report",
}

STAGE_ORDER: tuple[str, ...] = tuple(STAGE_LABELS.keys())


def get_progress_reporter() -> PipelineProgressReporter | None:
    """Return the active progress reporter for this async context, if any."""
    return _progress_reporter.get()


def set_progress_reporter(reporter: PipelineProgressReporter | None) -> Any:
    """Install or clear the active progress reporter. Returns a context token."""
    return _progress_reporter.set(reporter)


def reset_progress_reporter(token: Any) -> None:
    """Restore the previous progress reporter context."""
    _progress_reporter.reset(token)


def stage_label(stage_name: str) -> str:
    """Return a human-readable label for a pipeline stage."""
    return STAGE_LABELS.get(stage_name, stage_name.replace("_", " ").title())


@dataclass
class PipelineProgressReporter:
    """Rich-based live progress for research pipeline runs."""

    enabled: bool = True
    query: str = ""
    _console: Console = field(default_factory=lambda: Console(stderr=True, highlight=False))
    _live: Live | None = field(default=None, init=False, repr=False)
    _progress: Progress | None = field(default=None, init=False, repr=False)
    _stage_task_id: int | None = field(default=None, init=False, repr=False)
    _completed: list[tuple[str, float, bool]] = field(default_factory=list, init=False, repr=False)
    _current_stage: str = field(default="", init=False, repr=False)
    _activity: str = field(default="", init=False, repr=False)
    _llm_preview: str = field(default="", init=False, repr=False)
    _total_stages: int = field(default=len(STAGE_ORDER), init=False, repr=False)

    def __post_init__(self) -> None:
        self.enabled = self.enabled and sys.stderr.isatty()

    def attach(self, bus: PipelineEventBus) -> None:
        """Subscribe to pipeline stage lifecycle events."""
        bus.on_stage_start(self._on_stage_start)
        bus.on_stage_complete(self._on_stage_complete)

    def start(self, query: str) -> None:
        """Begin the live progress display."""
        self.query = query
        if not self.enabled:
            return

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=36),
            TextColumn("{task.completed}/{task.total}"),
            console=self._console,
            transient=False,
        )
        self._stage_task_id = self._progress.add_task(
            "Preparing research pipeline…",
            total=self._total_stages,
        )
        self._live = Live(
            self._build_renderable(),
            console=self._console,
            refresh_per_second=12,
            transient=False,
        )
        self._live.start()
        self._console.print(f"\n[bold]Research query:[/bold] {query}\n")

    def stop(self) -> None:
        """Stop the live display and print a summary line."""
        if not self.enabled or self._live is None:
            return

        self._live.stop()
        self._live = None
        elapsed = sum(duration for _, duration, _ in self._completed)
        partial = any(partial_flag for _, _, partial_flag in self._completed)
        status = "[yellow]partial[/yellow]" if partial else "[green]complete[/green]"
        self._console.print(
            f"\n[bold]Pipeline {status}[/bold] "
            f"({len(self._completed)} stages, {elapsed / 1000:.1f}s)\n"
        )

    def set_activity(self, message: str) -> None:
        """Update the sub-activity line (e.g. paper 2/5)."""
        self._activity = message.strip()
        self._refresh()

    def clear_activity(self) -> None:
        """Clear the sub-activity line."""
        self._activity = ""
        self._refresh()

    def set_llm_preview(self, text: str, *, max_chars: int = 280) -> None:
        """Show trailing LLM output while streaming."""
        cleaned = " ".join(text.split())
        if len(cleaned) > max_chars:
            cleaned = "…" + cleaned[-max_chars:]
        self._llm_preview = cleaned
        self._refresh()

    def clear_llm_preview(self) -> None:
        """Hide the LLM preview panel."""
        self._llm_preview = ""
        self._refresh()

    async def stream_agent_response(
        self,
        agent: Agent,
        prompt: str,
        *,
        label: str,
    ) -> str:
        """Run an agent with live token streaming when enabled."""
        if not self.enabled:
            result = await agent.run(prompt)
            return str(result.output)

        previous_activity = self._activity
        self.set_activity(label)
        chunks: list[str] = []
        try:
            async with agent.run_stream(prompt) as streamed:
                async for chunk in streamed.stream_text(delta=True):
                    if not chunk:
                        continue
                    chunks.append(chunk)
                    if len(chunks) % 2 == 0:
                        self.set_llm_preview("".join(chunks))
            return "".join(chunks)
        finally:
            self.clear_llm_preview()
            if previous_activity:
                self.set_activity(previous_activity)
            else:
                self.clear_activity()

    async def _on_stage_start(
        self,
        stage_name: str,
        _ctx: PipelineContext,
        _data: Any,
    ) -> None:
        self._current_stage = stage_name
        self._activity = ""
        self._llm_preview = ""
        if self.enabled and self._progress is not None and self._stage_task_id is not None:
            completed = len(self._completed)
            self._progress.update(
                self._stage_task_id,
                completed=completed,
                description=f"{stage_label(stage_name)}…",
            )
        self._refresh()

    async def _on_stage_complete(
        self,
        stage_name: str,
        _ctx: PipelineContext,
        result: StageResult[Any],
    ) -> None:
        self._completed.append((stage_name, result.duration_ms, result.partial))
        icon = "⚠" if result.partial else "✓"
        label = stage_label(stage_name)
        if self.enabled:
            style = "yellow" if result.partial else "green"
            self._console.print(
                f"  [{style}]{icon}[/{style}] {label} "
                f"[dim]({result.duration_ms:.0f} ms)[/dim]"
            )
            if self._progress is not None and self._stage_task_id is not None:
                self._progress.update(
                    self._stage_task_id,
                    completed=len(self._completed),
                )
        self._current_stage = ""
        self._activity = ""
        self._llm_preview = ""
        self._refresh()

    def _build_renderable(self) -> RenderableType:
        parts: list[RenderableType] = []
        if self._progress is not None:
            parts.append(self._progress)

        if self._activity:
            parts.append(Text(f"  → {self._activity}", style="italic cyan"))

        if self._llm_preview:
            parts.append(
                Panel(
                    Text(self._llm_preview, style="dim"),
                    title="[dim]AI generating…[/dim]",
                    border_style="dim",
                    padding=(0, 1),
                )
            )

        if not parts:
            table = Table.grid(padding=(0, 1))
            table.add_row(Text("Preparing…", style="cyan"))
            return table

        return Group(*parts)

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._build_renderable())


async def stream_agent_text(
    agent: Agent,
    prompt: str,
    *,
    label: str = "Thinking…",
) -> str:
    """Stream an agent response using the active reporter, or fall back to blocking run."""
    reporter = get_progress_reporter()
    if reporter is not None:
        return await reporter.stream_agent_response(agent, prompt, label=label)
    result = await agent.run(prompt)
    return str(result.output)
