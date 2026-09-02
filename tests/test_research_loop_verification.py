# -*- coding: utf-8 -*-
"""Tests for the iterative research loop and claim verification."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.analysis.verification import (
    VERIFICATION_ARTIFACT,
    VerificationStage,
    heuristic_unsupported,
)
from src.config.settings import AppSettings
from src.core.context import PipelineContext
from src.reporting.markdown import render_enhanced_markdown
from src.research.research_loop import (
    COVERAGE_ARTIFACT,
    CoverageAssessment,
    ResearchLoopStage,
    heuristic_coverage,
)
from src.retrieval.models import (
    EnhancedResearchReport,
    GapAnalysisResult,
    PaperAnalysis,
    RankedPaper,
    RetrievedPaper,
    VerificationSummary,
)


def _paper(title: str, abstract: str = "") -> RetrievedPaper:
    return RetrievedPaper(title=title, abstract=abstract or None, provider="test")


def _ranked(title: str, abstract: str = "", score: float = 0.8) -> RankedPaper:
    return RankedPaper(paper=_paper(title, abstract), rank_score=score, score_breakdown={})


class TestHeuristicCoverage:
    def test_sufficient_when_concepts_covered_and_enough_papers(self) -> None:
        papers = [
            _ranked(f"Transformer attention study {i}", "Attention mechanisms in transformers.")
            for i in range(6)
        ]
        assessment = heuristic_coverage(
            "transformer attention", papers, min_sufficient_papers=6
        )

        assert assessment.sufficient is True
        assert assessment.missing_aspects == []

    def test_missing_concept_generates_follow_up(self) -> None:
        papers = [_ranked("Transformer models overview", "Transformers for NLP.")] * 6
        assessment = heuristic_coverage(
            "transformer interpretability methods", papers, min_sufficient_papers=3
        )

        assert assessment.sufficient is False
        assert "interpretability" in assessment.missing_aspects
        assert any("interpretability" in q for q in assessment.follow_up_queries)

    def test_too_few_papers_is_insufficient(self) -> None:
        papers = [_ranked("Attention study", "attention transformers")]
        assessment = heuristic_coverage(
            "transformer attention", papers, min_sufficient_papers=6
        )
        assert assessment.sufficient is False


class TestResearchLoopStage:
    async def test_passthrough_when_disabled(self) -> None:
        settings = AppSettings(research_loop={"enabled": False})
        ctx = PipelineContext.create("query", settings)
        ranked = [_ranked("Paper")]

        result = await ResearchLoopStage().run(ctx, ranked)

        assert result.output == ranked
        assert result.metrics["iterations_run"] == 0

    async def test_no_iteration_when_coverage_sufficient(self) -> None:
        settings = AppSettings(research_loop={"enabled": True, "min_sufficient_papers": 1})
        ctx = PipelineContext.create("attention", settings)
        ranked = [_ranked("Attention study", "attention in models")]

        result = await ResearchLoopStage().run(ctx, ranked)

        assert result.metrics["iterations_run"] == 0
        assert result.metrics["coverage_sufficient"] is True
        assert ctx.get_artifact(COVERAGE_ARTIFACT)["sufficient"] is True

    async def test_insufficient_coverage_triggers_refinement(self) -> None:
        settings = AppSettings(research_loop={"enabled": True, "min_sufficient_papers": 1})
        ctx = PipelineContext.create("transformer interpretability", settings)
        seed = [_ranked("Transformer overview", "transformer architectures")]
        refined = seed + [
            _ranked(
                "Interpretability of transformers",
                "Probing and interpretability methods for transformer attention.",
            )
        ]

        async def fake_refine(self, ctx, current, follow_ups):
            assert any("interpretability" in q for q in follow_ups)
            return refined

        with patch.object(ResearchLoopStage, "_refine", fake_refine):
            result = await ResearchLoopStage().run(ctx, seed)

        assert result.metrics["iterations_run"] == 1
        assert result.metrics["papers_after_loop"] == 2
        assert result.metrics["coverage_sufficient"] is True
        assert ctx.get_artifact("ranked_papers") == refined

    async def test_iteration_budget_is_respected(self) -> None:
        settings = AppSettings(
            research_loop={"enabled": True, "max_iterations": 1, "min_sufficient_papers": 99}
        )
        ctx = PipelineContext.create("transformer interpretability", settings)
        seed = [_ranked("Transformer overview", "transformers")]

        calls = {"count": 0}

        async def fake_refine(self, ctx, current, follow_ups):
            calls["count"] += 1
            return current  # never improves

        with patch.object(ResearchLoopStage, "_refine", fake_refine):
            result = await ResearchLoopStage().run(ctx, seed)

        assert calls["count"] == 1
        assert result.metrics["iterations_run"] == 1
        assert result.metrics["coverage_sufficient"] is False

    async def test_refinement_failure_degrades_gracefully(self) -> None:
        settings = AppSettings(
            research_loop={"enabled": True, "min_sufficient_papers": 99}
        )
        ctx = PipelineContext.create("transformer interpretability", settings)
        seed = [_ranked("Transformer overview", "transformers")]

        async def failing_refine(self, ctx, current, follow_ups):
            raise RuntimeError("network down")

        with patch.object(ResearchLoopStage, "_refine", failing_refine):
            result = await ResearchLoopStage().run(ctx, seed)

        assert result.output == seed
        assert any("failed" in warning.lower() for warning in result.warnings)


class TestHeuristicVerification:
    def test_supported_claim_passes(self) -> None:
        sources = "attention mechanisms improve translation quality in transformers"
        unsupported = heuristic_unsupported(
            ["Attention improves translation quality"],
            sources,
            min_term_coverage=0.5,
        )
        assert unsupported == []

    def test_unrelated_claim_is_flagged(self) -> None:
        sources = "attention mechanisms improve translation quality"
        unsupported = heuristic_unsupported(
            ["Quantum error correction reduces decoherence"],
            sources,
            min_term_coverage=0.5,
        )
        assert unsupported == ["Quantum error correction reduces decoherence"]

    def test_no_sources_flags_nothing(self) -> None:
        assert heuristic_unsupported(["Any claim"], "", min_term_coverage=0.5) == []


class TestVerificationStage:
    def _ctx(self, analyses, ranked, passages=None, enabled=True):
        settings = AppSettings(verification={"enabled": enabled})
        ctx = PipelineContext.create("query", settings)
        ctx.set_artifact("paper_analyses", analyses)
        ctx.set_artifact("ranked_papers", ranked)
        if passages:
            ctx.set_artifact("fulltext_passages", passages)
        return ctx

    async def test_flags_unsupported_points_and_sets_summary(self) -> None:
        ranked = [_ranked("Attention Paper", "Attention improves translation quality.")]
        analysis = PaperAnalysis(
            paper_id=ranked[0].paper.paper_id,
            title="Attention Paper",
            key_points=[
                "Attention improves translation quality",
                "Quantum decoherence entangles qubits catastrophically",
            ],
        )
        ctx = self._ctx([analysis], ranked)

        result = await VerificationStage().run(ctx, GapAnalysisResult())

        updated = ctx.get_artifact("paper_analyses")[0]
        assert updated.unverified_points == [
            "Quantum decoherence entangles qubits catastrophically"
        ]
        summary = ctx.get_artifact(VERIFICATION_ARTIFACT)
        assert summary["claims_checked"] == 2
        assert summary["claims_unverified"] == 1
        assert result.metrics["method"] == "heuristic"

    async def test_passthrough_when_disabled(self) -> None:
        ctx = self._ctx([PaperAnalysis(title="T", key_points=["p"])], [], enabled=False)
        gap = GapAnalysisResult(gaps=["g"])

        result = await VerificationStage().run(ctx, gap)

        assert result.output is gap
        assert ctx.get_artifact(VERIFICATION_ARTIFACT) is None

    async def test_passages_extend_sources(self) -> None:
        ranked = [_ranked("Grounded Paper", "Short abstract.")]
        paper_id = ranked[0].paper.paper_id
        analysis = PaperAnalysis(
            paper_id=paper_id,
            title="Grounded Paper",
            key_points=["Sparse retrieval outperforms dense baselines on long tails"],
        )
        passages = {
            paper_id: [
                "Our experiments show sparse retrieval outperforms dense baselines "
                "on long-tail queries across benchmarks."
            ]
        }
        ctx = self._ctx([analysis], ranked, passages=passages)

        await VerificationStage().run(ctx, GapAnalysisResult())

        assert ctx.get_artifact("paper_analyses")[0].unverified_points == []


class TestReportRendering:
    def test_unverified_points_and_summary_render(self) -> None:
        report = EnhancedResearchReport(
            query="q",
            verification=VerificationSummary(
                claims_checked=3, claims_unverified=1, method="heuristic"
            ),
            papers=[
                PaperAnalysis(
                    paper_id="p1",
                    title="Paper",
                    key_points=["Solid claim", "Shaky claim"],
                    unverified_points=["Shaky claim"],
                )
            ],
            clusters=[],
        )
        report.clusters = [
            __import__("src.retrieval.models", fromlist=["PaperCluster"]).PaperCluster(
                theme="Theme", paper_ids=["p1"]
            )
        ]

        rendered = render_enhanced_markdown(report)

        assert "Claim verification (heuristic): 2/3" in rendered
        assert "- Shaky claim _(unverified)_" in rendered
        assert "- Solid claim\n" in rendered


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
