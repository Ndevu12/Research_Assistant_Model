# -*- coding: utf-8 -*-
"""Tests for enhanced markdown reporting and orchestrator facade."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.config.settings import AppSettings, RelevanceScoringConfig
from src.core.pipeline import ResearchPipelineResult
from src.reporting.citations import generate_bibtex, make_citation_key
from src.reporting.markdown import render_enhanced_markdown, render_markdown
from src.reporting.report_generation import (
    ReportGenerationStage,
    _build_executive_summary,
    _summary_embedding_floor,
    assemble_report,
)
from src.retrieval.models import (
    EnhancedResearchReport,
    GapAnalysisResult,
    PaperAnalysis,
    PaperCluster,
    RankedPaper,
    RetrievedPaper,
    ResearchReport,
    SynthesisResult,
)
from src.retrieval.orchestrator import build_pipeline, run_research_helper


def _sample_report() -> EnhancedResearchReport:
    return EnhancedResearchReport(
        query="transformer NLP models",
        executive_summary="Transformers dominate recent NLP research.",
        papers=[
            PaperAnalysis(
                paper_id="10.1000/a",
                title="Attention Is All You Need",
                year=2017,
                venue="NeurIPS",
                url="https://example.com/attention",
                key_points=["Introduced self-attention"],
                why_relevant=["Foundational transformer architecture"],
            )
        ],
        clusters=[
            PaperCluster(
                theme="Transformer Architectures",
                summary="Papers on attention-based sequence modeling.",
                paper_ids=["10.1000/a"],
            )
        ],
        synthesis=SynthesisResult(
            agreements=["Self-attention improves parallelization"],
            disagreements=["Optimal depth varies by task"],
            trends=["2017: 1 paper(s)"],
            gaps=["Limited low-resource evaluation"],
            datasets=["WMT"],
            methodologies=["Self-attention"],
        ),
        gap_analysis=GapAnalysisResult(
            gaps=["Limited low-resource evaluation"],
            opportunities=["Evaluate on African languages"],
            underexplored_areas=["Multilingual transfer"],
        ),
        gaps=["Limited low-resource evaluation"],
        timeline=["2017: 1 paper(s)"],
        citation_index={"10.1000/a": "vaswani2017attention"},
        exports={"bibtex": "@article{vaswani2017attention,\n  title = {Attention Is All You Need}\n}"},
    )


class TestMarkdownReporting:
    def test_render_enhanced_markdown_includes_thematic_sections(self) -> None:
        markdown = render_enhanced_markdown(_sample_report())

        assert "# Executive Summary" in markdown
        assert "# Thematic Findings" in markdown
        assert "Theme 1: Transformer Architectures" in markdown
        assert "# Methodology Comparison" in markdown
        assert "# Key Datasets & Benchmarks" in markdown
        assert "# Trends & Timeline" in markdown
        assert "# Agreements & Disagreements" in markdown
        assert "# Research Gaps & Opportunities" in markdown
        assert "# References" in markdown
        assert "[vaswani2017attention]" in markdown
        assert "# Appendix: All Papers" in markdown

    def test_render_enhanced_markdown_shows_partial_notice(self) -> None:
        markdown = render_enhanced_markdown(
            _sample_report(),
            partial=True,
            warnings=["Provider 'semantic_scholar' failed"],
        )

        assert "## Pipeline Notice" in markdown
        assert "partial pipeline results" in markdown
        assert "semantic_scholar" in markdown

    def test_render_markdown_legacy_format(self) -> None:
        legacy = ResearchReport(
            query="test",
            papers=[
                PaperAnalysis(
                    title="Legacy Paper",
                    key_points=["Point"],
                    why_relevant=["Relevant"],
                )
            ],
        )

        markdown = render_markdown(legacy)
        assert "# Research helper results" in markdown
        assert "Legacy Paper" in markdown

    def test_render_json_report(self) -> None:
        from src.reporting.json_report import render_json_report

        payload = render_json_report(_sample_report())
        assert '"query": "transformer NLP models"' in payload
        assert '"executive_summary"' in payload
        assert '"meta"' in payload

    def test_render_html_report(self) -> None:
        from src.reporting.html import render_html_report

        html = render_html_report(_sample_report())
        assert "<!DOCTYPE html>" in html
        assert "Executive Summary" in html
        assert "Transformer Architectures" in html


class TestCitationExport:
    def test_make_citation_key(self) -> None:
        paper = RetrievedPaper(
            title="Attention Is All You Need",
            year=2017,
            authors=["Ashish Vaswani"],
            provider="openalex",
        )
        assert make_citation_key(paper) == "vaswani2017attention"

    def test_generate_bibtex(self) -> None:
        paper = RetrievedPaper(
            title="Sample Paper",
            year=2024,
            authors=["Ada Lovelace"],
            doi="10.1000/sample",
            provider="openalex",
        )
        bibtex = generate_bibtex([paper])
        assert "@article{" in bibtex
        assert "Sample Paper" in bibtex


class TestExecutiveSummary:
    def test_executive_summary_uses_template_not_raw_agreement(self) -> None:
        clusters = [
            PaperCluster(theme="Transformer Architectures", paper_ids=["a"]),
            PaperCluster(theme="Attention Mechanisms", paper_ids=["b"]),
        ]
        synthesis = SynthesisResult(
            agreements=["Air pollutant transformer protein shows high affinity."],
        )
        ranked = [
            RankedPaper(
                paper=RetrievedPaper(title="Off-topic", provider="openalex"),
                rank_score=0.2,
                score_breakdown={"embedding_similarity": 0.1},
            )
        ]

        summary = _build_executive_summary(
            "transformer attention mechanisms",
            synthesis,
            clusters,
            paper_count=2,
            ranked_papers=ranked,
            relevance_config=RelevanceScoringConfig(min_embedding_similarity=0.35),
        )

        assert "transformer attention mechanisms" in summary
        assert "review of 2 paper(s)" in summary
        assert "Transformer Architectures" in summary
        assert "air pollutant" not in summary.lower()

    def test_executive_summary_appends_validated_finding_when_embedding_strong(self) -> None:
        clusters = [PaperCluster(theme="Transformers", paper_ids=["a"])]
        synthesis = SynthesisResult(
            agreements=["Self-attention improves parallel transformer training."],
        )
        ranked = [
            RankedPaper(
                paper=RetrievedPaper(title="Attention", provider="openalex"),
                rank_score=0.9,
                score_breakdown={"embedding_similarity": 0.8},
            )
        ]

        summary = _build_executive_summary(
            "transformer attention mechanisms",
            synthesis,
            clusters,
            paper_count=1,
            ranked_papers=ranked,
            relevance_config=RelevanceScoringConfig(min_embedding_similarity=0.35),
        )

        assert "Notable finding:" in summary
        assert "self-attention" in summary.lower()

    def test_executive_summary_omits_snippet_when_top_below_config_floor(self) -> None:
        """Snippet omitted when top embedding similarity is below configured floor."""
        clusters = [PaperCluster(theme="Transformers", paper_ids=["a"])]
        synthesis = SynthesisResult(
            agreements=["Self-attention improves parallel transformer training."],
        )
        ranked = [
            RankedPaper(
                paper=RetrievedPaper(title="Weak match", provider="openalex"),
                rank_score=0.4,
                score_breakdown={"embedding_similarity": 0.30},
            ),
        ]
        config = RelevanceScoringConfig(
            min_embedding_similarity=0.35,
            adaptive_embedding=True,
            gap_from_top=0.12,
        )

        summary = _build_executive_summary(
            "transformer attention mechanisms",
            synthesis,
            clusters,
            paper_count=1,
            ranked_papers=ranked,
            relevance_config=config,
        )

        assert "Notable finding:" not in summary
        assert "transformer attention mechanisms" in summary

    def test_summary_embedding_floor_matches_relevance_scoring(self) -> None:
        ranked = [
            RankedPaper(
                paper=RetrievedPaper(title="A", provider="openalex"),
                rank_score=0.9,
                score_breakdown={"embedding_similarity": 0.92},
            ),
            RankedPaper(
                paper=RetrievedPaper(title="B", provider="openalex"),
                rank_score=0.5,
                score_breakdown={"embedding_similarity": 0.55},
            ),
        ]
        config = RelevanceScoringConfig(
            min_embedding_similarity=0.35,
            adaptive_embedding=True,
            gap_from_top=0.12,
            keep_percentile=25.0,
        )

        floor = _summary_embedding_floor(ranked, config)

        assert floor == pytest.approx(0.80, abs=0.01)


class TestReportGenerationStage:
    @pytest.mark.asyncio
    async def test_assemble_report_from_context_artifacts(self) -> None:
        from src.core.context import PipelineContext
        from src.config.settings import AppSettings
        from src.retrieval.models import RankedPaper

        ctx = PipelineContext.create("transformers", AppSettings())
        ctx.set_artifact(
            "ranked_papers",
            [
                RankedPaper(
                    paper=RetrievedPaper(
                        title="Attention",
                        year=2017,
                        doi="10.1000/a",
                        provider="openalex",
                    ),
                    rank_score=0.9,
                )
            ],
        )
        ctx.set_artifact(
            "paper_analyses",
            [PaperAnalysis(paper_id="10.1000/a", title="Attention", year=2017)],
        )
        ctx.set_artifact(
            "paper_clusters",
            [PaperCluster(theme="Transformers", paper_ids=["10.1000/a"])],
        )
        ctx.set_artifact(
            "synthesis_result",
            SynthesisResult(agreements=["Shared attention theme"]),
        )
        ctx.set_artifact(
            "gap_analysis",
            GapAnalysisResult(gaps=["Need broader benchmarks"]),
        )
        ctx.set_artifact("citation_index", {"10.1000/a": "anon2017attention"})

        stage = ReportGenerationStage()
        result = await stage.run(ctx, {"bibtex": "@article{key}"})

        assert isinstance(result.output, EnhancedResearchReport)
        assert result.output.query == "transformers"
        assert result.output.gap_analysis is not None
        assert result.output.citation_index["10.1000/a"] == "anon2017attention"


class TestOrchestratorFacade:
    def test_build_pipeline_includes_report_stages(self) -> None:
        pipeline = build_pipeline(AppSettings())
        stage_names = [stage.name for stage in pipeline.stages]

        assert "query_understanding" in stage_names
        assert "retrieval" in stage_names
        assert "citation_export" in stage_names
        assert "report_generation" in stage_names

    @pytest.mark.asyncio
    async def test_run_research_helper_prints_enhanced_report(self, capsys) -> None:
        report = _sample_report()
        pipeline_result = ResearchPipelineResult(
            query=report.query,
            output=report,
            session_id="test-session",
            partial=False,
        )

        with patch(
            "src.retrieval.orchestrator.run_research_with_result",
            new=AsyncMock(return_value=(report, pipeline_result)),
        ):
            await run_research_helper("transformer NLP models")

        captured = capsys.readouterr()
        assert "# Executive Summary" in captured.out
        assert "Transformer Architectures" in captured.out

    @pytest.mark.asyncio
    async def test_run_research_helper_no_results(self, capsys) -> None:
        empty_report = EnhancedResearchReport(query="empty query")
        pipeline_result = ResearchPipelineResult(
            query="empty query",
            output=empty_report,
            session_id="test-session",
        )

        with patch(
            "src.retrieval.orchestrator.run_research_with_result",
            new=AsyncMock(return_value=(empty_report, pipeline_result)),
        ):
            await run_research_helper("empty query")

        captured = capsys.readouterr()
        assert "No papers found" in captured.out
