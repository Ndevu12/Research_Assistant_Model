# -*- coding: utf-8 -*-
"""Orchestrator facade for the composable research pipeline."""

from __future__ import annotations

from typing import Optional

from ..analysis.gap_analysis import GapAnalysisStage
from ..analysis.synthesis import SynthesisStage
from ..config.settings import AppSettings
from ..core.context import ResearchSession
from ..core.events import get_event_bus
from ..core.pipeline import ResearchPipeline, ResearchPipelineResult
from ..reporting.output import render_report_output
from ..memory.store import MemoryStore, build_cache_key, build_config_hash
from ..reporting.citations import CitationExportStage
from ..reporting.markdown import render_enhanced_markdown
from ..reporting.report_generation import ReportGenerationStage
from ..research.clustering import ClusteringStage
from ..research.query_expansion import QueryExpansionStage
from ..research.query_understanding import QueryUnderstandingStage
from ..research.ranking import RankingStage
from ..research.relevance_scoring import RelevanceScoringStage
from ..retrieval.deduplication import DeduplicationStage
from ..retrieval.snowball import SnowballStage
from ..retrieval.models import (
    EnhancedResearchReport,
    ExpandedQuerySet,
    RankedPaper,
    RetrievedPaper,
)
from ..retrieval.retrieval_stage import RetrievalStage
from ..utils.message_formatter import MessageFormatter
from ..utils.progress_reporter import (
    PipelineProgressReporter,
    reset_progress_reporter,
    set_progress_reporter,
)


def build_pipeline(settings: AppSettings) -> ResearchPipeline:
    """Construct the default research pipeline from application settings."""
    return ResearchPipeline(
        [
            QueryUnderstandingStage(),
            QueryExpansionStage(),
            RetrievalStage(),
            DeduplicationStage(),
            RankingStage(),
            SnowballStage(),
            RelevanceScoringStage(),
            ClusteringStage(),
            SynthesisStage(),
            GapAnalysisStage(),
            CitationExportStage(),
            ReportGenerationStage(),
        ],
        settings,
    )


def _resolve_expanded_queries(result: ResearchPipelineResult, query: str) -> list[str]:
    """Collect expanded query variants generated during the run."""
    artifact = result.artifacts.get("expanded_queries")
    if isinstance(artifact, ExpandedQuerySet):
        expanded = [*artifact.variants, *artifact.sub_questions]
    elif isinstance(artifact, dict):
        expanded = [
            *artifact.get("variants", []),
            *artifact.get("sub_questions", []),
        ]
    else:
        expanded = []
    return [item for item in dict.fromkeys(expanded) if item and item != query]


def _resolve_report(result: ResearchPipelineResult, query: str) -> EnhancedResearchReport:
    report = result.output
    if isinstance(report, EnhancedResearchReport):
        return report
    artifact = result.artifacts.get("enhanced_report")
    if artifact:
        return EnhancedResearchReport.model_validate(artifact)
    return EnhancedResearchReport(query=query)


async def _persist_memory(
    store: MemoryStore,
    session: ResearchSession,
    query: str,
    result: ResearchPipelineResult,
    report: EnhancedResearchReport,
    settings: AppSettings,
) -> None:
    """Save search, papers, and report to the memory store."""
    enabled_providers = [name for name, cfg in settings.retrieval.providers.items() if cfg.enabled]
    cache_key = build_cache_key(query, enabled_providers, build_config_hash(settings))

    expanded = _resolve_expanded_queries(result, query)
    search_id = await store.save_search(
        session.id,
        query,
        expanded_queries=expanded,
        cache_key=cache_key,
    )

    ranked = result.artifacts.get("ranked_papers") or []
    papers: list[RetrievedPaper] = []
    for item in ranked:
        if isinstance(item, RankedPaper):
            papers.append(item.paper)
        elif isinstance(item, dict):
            papers.append(RetrievedPaper.model_validate(item["paper"]))

    if not papers:
        retrieved = result.artifacts.get("retrieved_papers") or []
        papers = [RetrievedPaper.model_validate(item) for item in retrieved]

    if papers:
        await store.save_papers(search_id, papers)

    markdown = render_enhanced_markdown(
        report,
        partial=result.partial,
        warnings=result.warnings,
        citation_index=report.citation_index,
        gap_analysis=report.gap_analysis,
    )
    await store.save_report(session.id, "markdown", markdown)


async def run_research(
    query: str,
    settings: AppSettings | None = None,
    session: ResearchSession | None = None,
    store: MemoryStore | None = None,
) -> EnhancedResearchReport:
    """Run the full research pipeline and return an enhanced report."""
    report, _ = await run_research_with_result(
        query,
        settings=settings,
        session=session,
        store=store,
    )
    return report


async def run_research_with_result(
    query: str,
    settings: AppSettings | None = None,
    session: ResearchSession | None = None,
    store: MemoryStore | None = None,
    *,
    stream_progress: bool | None = None,
) -> tuple[EnhancedResearchReport, ResearchPipelineResult]:
    """Run the pipeline and return both the report and full pipeline metadata."""
    resolved_settings = settings or AppSettings()
    resolved_session = session or ResearchSession(last_query=query)
    resolved_store = store

    if resolved_store is None and resolved_settings.memory.cache_enabled:
        resolved_store = MemoryStore(resolved_settings.memory)
        await resolved_store.initialize()

    cache_hit_papers: list[dict] | None = None
    if resolved_store and resolved_settings.memory.cache_enabled:
        enabled_providers = [
            name for name, cfg in resolved_settings.retrieval.providers.items() if cfg.enabled
        ]
        cache_key = build_cache_key(query, enabled_providers, build_config_hash(resolved_settings))
        cached = await resolved_store.get_cached_search(cache_key)
        if cached:
            cache_hit_papers = cached.papers

    show_progress = (
        stream_progress
        if stream_progress is not None
        else resolved_settings.pipeline.stream_progress
    )
    reporter = PipelineProgressReporter(enabled=show_progress)
    reporter.attach(get_event_bus())
    token = set_progress_reporter(reporter)
    reporter.start(query)

    try:
        pipeline = build_pipeline(resolved_settings)
        initial_artifacts = {"cached_papers": cache_hit_papers} if cache_hit_papers else None
        result = await pipeline.execute(
            query,
            session=resolved_session,
            initial_artifacts=initial_artifacts,
        )
    finally:
        reporter.stop()
        reset_progress_reporter(token)

    report = _resolve_report(result, query)

    if resolved_store:
        await _persist_memory(
            resolved_store,
            resolved_session,
            query,
            result,
            report,
            resolved_settings,
        )

    return report, result


async def run_research_helper(
    user_text: str,
    k_each: int = 8,
    *,
    return_report: bool = False,
    output_format: str = "markdown",
    export_formats: list[str] | None = None,
    output_path: str | None = None,
    session: ResearchSession | None = None,
    store: MemoryStore | None = None,
    stream_progress: bool | None = None,
) -> Optional[EnhancedResearchReport]:
    """Run the research helper and print a report by default.

    When ``return_report`` is True, returns the :class:`EnhancedResearchReport`
    instead of printing.
    """
    settings = AppSettings(
        retrieval={
            "per_provider_limit": k_each,
            "providers": {
                "openalex": {"enabled": True, "limit": k_each},
                "semantic_scholar": {"enabled": True, "limit": k_each},
            },
        }
    )

    from ..utils import console as ui

    try:
        report, result = await run_research_with_result(
            user_text,
            settings=settings,
            session=session,
            store=store,
            stream_progress=stream_progress,
        )
    except Exception as exc:
        ui.print_error(MessageFormatter.network_error(str(exc)))
        return None

    if not report.papers and not result.partial:
        ui.print_notice(MessageFormatter.no_results_message())
        return report if return_report else None

    rendered = render_report_output(
        report,
        output_format=output_format,
        partial=result.partial,
        warnings=result.warnings,
        export_formats=export_formats,
    )

    if output_path:
        from pathlib import Path

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        ui.print_notice(f"Report written to {path.resolve()}")
        if output_format == "pdf":
            ui.print_notice(
                "PDF-ready HTML saved. Open in a browser and use Print → Save as PDF."
            )
    else:
        if output_format in {"html", "pdf"}:
            ui.print_notice(
                "Tip: use --output report.html with --format pdf to save print-ready HTML."
            )
        ui.print_report(rendered, output_format)

    if export_formats:
        from ..export import generate_citation_exports
        from ..retrieval.models import RankedPaper

        ranked_raw = result.artifacts.get("ranked_papers") or []
        papers = [
            RankedPaper.model_validate(item).paper for item in ranked_raw
        ] if ranked_raw else []
        if papers:
            exports = generate_citation_exports(papers, formats=export_formats)
            for fmt in export_formats:
                content = exports.get(fmt)
                if content:
                    ui.print_citation_export(fmt, content)

    if return_report:
        return report
    return None
