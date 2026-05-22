# -*- coding: utf-8 -*-
"""Interactive research session with memory persistence and follow-up filters."""

from __future__ import annotations

from ..config.settings import AppSettings
from ..core.context import ResearchSession
from ..core.pipeline import ResearchPipelineResult
from ..export import SUPPORTED_FORMATS, generate_citation_exports
from ..reporting.markdown import render_enhanced_markdown
from ..retrieval.models import EnhancedResearchReport, RankedPaper, RetrievedPaper
from ..reporting.output import render_report_output
from .filters import (
    FollowUpCommand,
    FollowUpIntent,
    analyses_from_ranked,
    boost_ranked_papers,
    filter_ranked_papers,
    filter_report_analyses,
    follow_up_help_text,
    parse_follow_up,
)
from .store import MemoryStore


def _extract_ranked_papers(pipeline_result: ResearchPipelineResult) -> list[RankedPaper]:
    """Extract ranked papers from pipeline artifacts."""
    raw = pipeline_result.artifacts.get("ranked_papers")
    if not raw:
        return []
    papers: list[RankedPaper] = []
    for item in raw:
        if isinstance(item, RankedPaper):
            papers.append(item)
        else:
            papers.append(RankedPaper.model_validate(item))
    return papers


class InteractiveResearchSession:
    """Session-aware research runner with SQLite memory and follow-up support."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        store: MemoryStore | None = None,
        session: ResearchSession | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.store = store or MemoryStore(self.settings.memory)
        self.session = session or ResearchSession()
        self.last_report: EnhancedResearchReport | None = None
        self.last_ranked_papers: list[RankedPaper] = []
        self.last_pipeline_result: ResearchPipelineResult | None = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        await self.store.initialize()
        stored = await self.store.load_session(self.session.id)
        if stored is None:
            self.session = await self.store.create_session(self.session)
        else:
            self.session = self.store.session_from_stored(stored)
            self._restore_from_context()
        self._initialized = True

    def _restore_from_context(self) -> None:
        context = self.session.context_json
        if context.get("last_report"):
            self.last_report = EnhancedResearchReport.model_validate(context["last_report"])
        if context.get("last_ranked_papers"):
            self.last_ranked_papers = [
                RankedPaper.model_validate(item) for item in context["last_ranked_papers"]
            ]

    async def _persist_state(self) -> None:
        self.session.context_json = {
            "last_report": self.last_report.model_dump() if self.last_report else None,
            "last_ranked_papers": [item.model_dump() for item in self.last_ranked_papers],
        }
        await self.store.update_session(self.session)

    async def run_full_query(
        self,
        query: str,
        *,
        output_format: str = "markdown",
        export_formats: list[str] | None = None,
        stream_progress: bool | None = None,
    ) -> str:
        """Run the full pipeline for a new query and return rendered output."""
        from ..retrieval.orchestrator import run_research_with_result

        self.session.last_query = query

        report, pipeline_result = await run_research_with_result(
            query,
            settings=self.settings,
            session=self.session,
            store=self.store,
            stream_progress=stream_progress,
        )

        self.last_report = report
        self.last_pipeline_result = pipeline_result
        self.last_ranked_papers = _extract_ranked_papers(pipeline_result)

        rendered = await self._render_and_persist(
            report,
            pipeline_result,
            output_format=output_format,
            export_formats=export_formats,
        )
        await self._persist_state()
        return rendered

    async def handle_follow_up(
        self,
        text: str,
        *,
        output_format: str = "markdown",
        export_formats: list[str] | None = None,
    ) -> str | None:
        """Handle a follow-up command. Returns None when a new query should run."""
        command = parse_follow_up(text)

        if command.intent == FollowUpIntent.NEW_QUERY:
            return None

        if command.intent == FollowUpIntent.HELP:
            return follow_up_help_text()

        if self.last_report is None or not self.last_ranked_papers:
            return "No previous research results in this session. Enter a research query first."

        if command.intent == FollowUpIntent.EXPORT:
            return self._render_exports(command.export_formats or list(SUPPORTED_FORMATS))

        if command.intent == FollowUpIntent.FILTER:
            return self._apply_filter(command, output_format=output_format)

        if command.intent == FollowUpIntent.FOCUS:
            return self._apply_focus(command, output_format=output_format)

        if command.intent == FollowUpIntent.COMPARE:
            return self._apply_compare(output_format=output_format)

        return None

    def _apply_filter(self, command: FollowUpCommand, *, output_format: str) -> str:
        assert command.filter_criteria is not None
        assert self.last_report is not None

        filtered_ranked = filter_ranked_papers(self.last_ranked_papers, command.filter_criteria)
        if not filtered_ranked:
            return "No papers matched your filter criteria."

        allowed_ids = {item.paper.paper_id for item in filtered_ranked}
        filtered_report = filter_report_analyses(self.last_report, allowed_ids)
        filtered_report = filtered_report.model_copy(
            update={
                "papers": analyses_from_ranked(filtered_ranked, self.last_report.papers),
            }
        )
        return self._render_local_report(filtered_report, output_format=output_format)

    def _apply_focus(self, command: FollowUpCommand, *, output_format: str) -> str:
        assert command.focus_keywords is not None
        assert self.last_report is not None

        reranked = boost_ranked_papers(self.last_ranked_papers, command.focus_keywords)
        allowed_ids = {item.paper.paper_id for item in reranked}
        focused_report = filter_report_analyses(self.last_report, allowed_ids)
        focused_report = focused_report.model_copy(
            update={
                "papers": analyses_from_ranked(reranked, self.last_report.papers),
                "executive_summary": (
                    f"Re-ranked by focus keywords ({', '.join(command.focus_keywords)}): "
                    f"{focused_report.executive_summary}"
                ),
            }
        )
        return self._render_local_report(focused_report, output_format=output_format)

    def _apply_compare(self, *, output_format: str) -> str:
        assert self.last_report is not None
        synthesis = self.last_report.synthesis
        if output_format == "markdown":
            lines = ["# Methodology Comparison", ""]
            if synthesis and synthesis.methodologies:
                lines.extend(f"- {item}" for item in synthesis.methodologies)
            else:
                lines.append("_No cross-paper methodology synthesis available._")
            return "\n".join(lines) + "\n"
        return self._render_local_report(self.last_report, output_format=output_format)

    def _render_exports(self, formats: list[str]) -> str:
        assert self.last_report is not None

        retrieved: list[RetrievedPaper] = [item.paper for item in self.last_ranked_papers]
        if not retrieved:
            for analysis in self.last_report.papers:
                retrieved.append(
                    RetrievedPaper(
                        title=analysis.title,
                        year=analysis.year,
                        venue=analysis.venue,
                        url=analysis.url,
                        doi=analysis.doi,
                        provider="session",
                    )
                )

        exports = generate_citation_exports(retrieved, formats=formats)
        sections: list[str] = ["# Citation Export", ""]
        for fmt in formats:
            content = exports.get(fmt, "")
            if content:
                sections.extend([f"## {fmt.upper()}", "", content, ""])
        return "\n".join(sections).rstrip() + "\n"

    def _render_local_report(self, report: EnhancedResearchReport, *, output_format: str) -> str:
        partial = self.last_pipeline_result.partial if self.last_pipeline_result else False
        warnings = list(self.last_pipeline_result.warnings) if self.last_pipeline_result else []
        return render_report_output(
            report,
            output_format=output_format,
            partial=partial,
            warnings=warnings,
        )

    async def _render_and_persist(
        self,
        report: EnhancedResearchReport,
        pipeline_result: ResearchPipelineResult,
        *,
        output_format: str,
        export_formats: list[str] | None,
    ) -> str:
        rendered = render_report_output(
            report,
            output_format=output_format,
            partial=pipeline_result.partial,
            warnings=pipeline_result.warnings,
            export_formats=export_formats,
        )
        await self.store.save_report(self.session.id, output_format, rendered)
        return rendered
