# -*- coding: utf-8 -*-
"""Tests for cross-paper synthesis and gap analysis."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analysis.gap_analysis import (
    GapAnalysisStage,
    analyze_gaps,
    recover_gap_analysis_output,
    resolve_synthesis_input,
    _heuristic_gap_analysis,
)
from src.analysis.synthesis import (
    HEURISTIC_DISAGREEMENT_PLACEHOLDER,
    SynthesisStage,
    _heuristic_extraction,
    _heuristic_synthesis,
    extract_papers,
    recover_synthesis_output,
    run_synthesis,
    synthesize_collective,
)
from src.core.stage_recovery import recover_stage_output
from src.config.settings import AppSettings, LLMConfig
from src.core.context import PipelineContext
from src.core.pipeline import ResearchPipeline
from src.research.clustering import ClusteringStage
from pydantic import ValidationError

from src.retrieval.models import (
    GapAnalysisResult,
    PaperCluster,
    PaperExtraction,
    RankedPaper,
    RetrievedPaper,
    SynthesisResult,
)

STRUCTURED_TARGET = "src.models.structured.try_run_structured"


def _paper(title: str, **kwargs: object) -> RetrievedPaper:
    return RetrievedPaper(title=title, provider="openalex", **kwargs)


def _ranked(title: str, **kwargs: object) -> RankedPaper:
    score_breakdown = kwargs.pop("score_breakdown", {})
    return RankedPaper(
        paper=_paper(title, **kwargs),
        rank_score=0.9,
        score_breakdown=score_breakdown,
    )


def _structured_mock(*results: object) -> AsyncMock:
    """AsyncMock standing in for try_run_structured.

    With one result it is returned for every call; with several they are
    consumed in call order. ``None`` triggers the caller's heuristic fallback,
    exactly like a failed structured call.
    """
    if len(results) == 1:
        return AsyncMock(return_value=results[0])
    return AsyncMock(side_effect=list(results))


def _llm_synthesis_config(**overrides: object):
    config = {
        "llm_enabled": True,
        "max_llm_papers": 10,
        "concurrency": 2,
    }
    config.update(overrides)
    return AppSettings(synthesis=config).synthesis


class TestSynthesisModels:
    def test_synthesis_result_schema_accepts_all_fields(self) -> None:
        synthesis = SynthesisResult(
            agreements=["Shared transformer adoption"],
            disagreements=["CNN vs transformer on small data"],
            trends=["Shift toward pre-training"],
            gaps=["Limited multilingual evaluation"],
            datasets=["GLUE", "SQuAD"],
            methodologies=["Self-attention", "Fine-tuning"],
        )

        assert synthesis.model_dump() == {
            "agreements": ["Shared transformer adoption"],
            "disagreements": ["CNN vs transformer on small data"],
            "trends": ["Shift toward pre-training"],
            "gaps": ["Limited multilingual evaluation"],
            "datasets": ["GLUE", "SQuAD"],
            "methodologies": ["Self-attention", "Fine-tuning"],
        }

    def test_synthesis_result_schema_defaults_to_empty_lists(self) -> None:
        synthesis = SynthesisResult()

        assert synthesis.agreements == []
        assert synthesis.disagreements == []
        assert synthesis.trends == []
        assert synthesis.gaps == []
        assert synthesis.datasets == []
        assert synthesis.methodologies == []

    def test_synthesis_result_schema_rejects_invalid_field_types(self) -> None:
        with pytest.raises(ValidationError):
            SynthesisResult(agreements="not-a-list")  # type: ignore[arg-type]

    def test_synthesis_result_round_trips_through_json(self) -> None:
        original = SynthesisResult(
            agreements=["Agreement"],
            gaps=["Gap"],
            methodologies=["Method"],
        )

        restored = SynthesisResult.model_validate_json(original.model_dump_json())

        assert restored == original

    def test_paper_extraction_schema(self) -> None:
        extraction = PaperExtraction(
            paper_id="10.1000/a",
            title="Transformer Study",
            methodology=["Self-attention"],
            datasets=["WMT"],
            benchmarks=["BLEU"],
            limitations=["Small sample"],
            findings=["Outperforms RNN baselines"],
        )

        assert extraction.paper_id == "10.1000/a"
        assert extraction.findings == ["Outperforms RNN baselines"]

    def test_gap_analysis_result_schema(self) -> None:
        result = GapAnalysisResult(
            gaps=["Limited multilingual evaluation"],
            opportunities=["Benchmark on low-resource languages"],
            underexplored_areas=["Cross-lingual transfer"],
        )

        assert len(result.opportunities) == 1


class TestHeuristicSynthesis:
    def test_heuristic_extraction_uses_abstract(self) -> None:
        ranked = _ranked(
            "Attention paper",
            abstract="We propose attention. It works well. Limited to English.",
        )
        extraction = _heuristic_extraction(ranked)

        assert extraction.title == "Attention paper"
        assert len(extraction.findings) >= 1

    def test_heuristic_synthesis_aggregates_extractions(self) -> None:
        extractions = [
            PaperExtraction(
                paper_id="a",
                title="Paper A",
                methodology=["Transformers"],
                datasets=["GLUE"],
                findings=["Strong accuracy"],
                limitations=["English only"],
            ),
            PaperExtraction(
                paper_id="b",
                title="Paper B",
                methodology=["Transformers"],
                datasets=["SQuAD"],
                findings=["Good F1"],
                limitations=["High compute"],
            ),
        ]
        clusters = [
            PaperCluster(theme="Transformers", summary="NLP papers", paper_ids=["a", "b"]),
        ]

        synthesis = _heuristic_synthesis("transformers NLP", extractions, clusters)

        assert isinstance(synthesis, SynthesisResult)
        assert synthesis.datasets
        assert synthesis.methodologies
        assert synthesis.gaps
        assert synthesis.disagreements == [HEURISTIC_DISAGREEMENT_PLACEHOLDER]

    def test_heuristic_synthesis_prefers_top_embedding_quartile(self) -> None:
        ranked = [
            _ranked(
                "On-topic transformer",
                doi="10.1000/on-topic",
                abstract="Self-attention improves transformer NLP models.",
                score_breakdown={"embedding_similarity": 0.9},
            ),
            _ranked(
                "Off-topic air pollution",
                doi="10.1000/off-topic",
                abstract="Air pollutant transformer protein binding.",
                score_breakdown={"embedding_similarity": 0.1},
            ),
        ]
        extractions = [
            PaperExtraction(
                paper_id="10.1000/on-topic",
                title="On-topic transformer",
                findings=["Self-attention enables parallel transformer training."],
            ),
            PaperExtraction(
                paper_id="10.1000/off-topic",
                title="Off-topic air pollution",
                findings=["Air pollutant transformer protein shows high affinity."],
            ),
        ]
        clusters = [
            PaperCluster(
                theme="Transformers",
                summary="NLP papers",
                paper_ids=["10.1000/on-topic"],
            ),
        ]

        synthesis = _heuristic_synthesis(
            "transformer attention mechanisms",
            extractions,
            clusters,
            ranked_papers=ranked,
        )

        assert synthesis.agreements
        assert "transformer" in synthesis.agreements[0].lower()
        assert "air pollutant" not in " ".join(synthesis.agreements).lower()

    def test_heuristic_synthesis_reports_conflicts_when_detected(self) -> None:
        extractions = [
            PaperExtraction(
                paper_id="a",
                title="Paper A",
                findings=["The model outperforms all baselines."],
            ),
            PaperExtraction(
                paper_id="b",
                title="Paper B",
                findings=["The approach underperforms existing methods."],
            ),
        ]

        synthesis = _heuristic_synthesis("model comparison", extractions, [])

        assert synthesis.disagreements
        assert synthesis.disagreements != [HEURISTIC_DISAGREEMENT_PLACEHOLDER]

    def test_heuristic_gap_analysis_expands_synthesis(self) -> None:
        synthesis = SynthesisResult(
            gaps=["No multilingual benchmarks"],
            disagreements=["CNN vs transformer on small data"],
            trends=["Shift toward pre-training"],
        )
        clusters = [PaperCluster(theme="Efficiency", summary="Small models", paper_ids=["x"])]

        result = _heuristic_gap_analysis(synthesis, "NLP", clusters)

        assert "No multilingual benchmarks" in result.gaps
        assert result.opportunities


class TestSynthesisWorkflow:
    @pytest.mark.asyncio
    async def test_extract_papers_uses_structured_llm(self) -> None:
        ranked = [_ranked("Paper One", abstract="Findings here.")]
        expected = PaperExtraction(
            paper_id="Paper One",
            title="Paper One",
            findings=["Finding"],
        )
        structured = _structured_mock(expected)

        with patch(STRUCTURED_TARGET, structured):
            extractions = await extract_papers(
                ranked,
                "test query",
                concurrency=1,
                synthesis_config=_llm_synthesis_config(max_llm_papers=1),
            )

        assert len(extractions) == 1
        assert extractions[0].title == "Paper One"
        structured.assert_awaited()

    @pytest.mark.asyncio
    async def test_extract_papers_falls_back_on_llm_failure(self) -> None:
        ranked = [_ranked("Paper Two", abstract="Some results.")]

        with patch(STRUCTURED_TARGET, _structured_mock(None)):
            extractions = await extract_papers(
                ranked,
                "test query",
                concurrency=1,
                synthesis_config=_llm_synthesis_config(max_llm_papers=1),
            )

        assert len(extractions) == 1
        assert extractions[0].title == "Paper Two"

    @pytest.mark.asyncio
    async def test_synthesize_collective_validates_schema(self) -> None:
        extractions = [
            PaperExtraction(paper_id="a", title="A", findings=["Result"]),
        ]
        expected = SynthesisResult(
            agreements=["Shared transformer usage"],
            gaps=["Need more benchmarks"],
        )

        with patch(STRUCTURED_TARGET, _structured_mock(expected)):
            synthesis = await synthesize_collective(
                "transformers",
                extractions,
                [],
                synthesis_config=_llm_synthesis_config(),
            )

        assert synthesis.agreements == ["Shared transformer usage"]
        assert synthesis.gaps == ["Need more benchmarks"]

    @pytest.mark.asyncio
    async def test_run_synthesis_two_pass_workflow(self) -> None:
        ranked = [
            _ranked("Paper A", abstract="Method A findings."),
            _ranked("Paper B", abstract="Method B findings."),
        ]
        clusters = [PaperCluster(theme="Methods", summary="Comparison", paper_ids=["Paper A", "Paper B"])]

        extraction_a = PaperExtraction(paper_id="Paper A", title="Paper A", findings=["A"])
        extraction_b = PaperExtraction(paper_id="Paper B", title="Paper B", findings=["B"])
        synthesis = SynthesisResult(agreements=["Both use deep learning"], gaps=["Scale"])
        structured = _structured_mock(extraction_a, extraction_b, synthesis)

        with patch(STRUCTURED_TARGET, structured):
            result, extractions, analyses = await run_synthesis(
                "deep learning",
                ranked,
                clusters,
                concurrency=2,
                synthesis_config=_llm_synthesis_config(max_llm_papers=2),
            )

        assert len(extractions) == 2
        assert result.agreements == ["Both use deep learning"]
        assert len(analyses) == 2
        assert structured.await_count == 3


class TestGapAnalysis:
    @pytest.mark.asyncio
    async def test_analyze_gaps_uses_structured_llm(self) -> None:
        synthesis = SynthesisResult(gaps=["Missing ablations"])
        expected = GapAnalysisResult(
            gaps=["Missing ablations"],
            opportunities=["Run systematic ablations"],
        )

        with patch(STRUCTURED_TARGET, _structured_mock(expected)):
            result = await analyze_gaps("query", synthesis, llm_config=LLMConfig())

        assert result.opportunities == ["Run systematic ablations"]

    @pytest.mark.asyncio
    async def test_analyze_gaps_heuristic_fallback(self) -> None:
        synthesis = SynthesisResult(gaps=["Understudied domain"])

        with patch(STRUCTURED_TARGET, _structured_mock(None)):
            result = await analyze_gaps("query", synthesis, llm_config=LLMConfig())

        assert "Understudied domain" in result.gaps
        assert result.opportunities


class TestSynthesisPipelineStages:
    @pytest.mark.asyncio
    async def test_synthesis_stage_records_artifacts(self) -> None:
        ranked = [_ranked("Stage Paper", abstract="Results.")]
        clusters = [PaperCluster(theme="Theme", summary="Summary", paper_ids=["Stage Paper"])]
        ctx = PipelineContext.create("stage test", AppSettings())
        ctx.set_artifact("ranked_papers", ranked)

        extraction = PaperExtraction(paper_id="Stage Paper", title="Stage Paper", findings=["F"])
        synthesis = SynthesisResult(agreements=["Agreement"], gaps=["Gap"])

        stage = SynthesisStage()
        with patch(STRUCTURED_TARGET, _structured_mock(extraction, synthesis)):
            result = await stage.run(ctx, clusters)

        assert isinstance(result.output, SynthesisResult)
        assert ctx.get_artifact("paper_extractions") is not None
        assert ctx.get_artifact("paper_analyses") is not None
        assert result.metrics["papers_extracted"] == 1

    @pytest.mark.asyncio
    async def test_gap_analysis_stage(self) -> None:
        synthesis = SynthesisResult(gaps=["Gap one"])
        ctx = PipelineContext.create(
            "gap stage",
            AppSettings(synthesis={"llm_enabled": True}),
        )
        ctx.set_artifact("paper_clusters", [PaperCluster(theme="T", paper_ids=["p1"])])

        gap_result = GapAnalysisResult(
            gaps=["Gap one"],
            opportunities=["Opportunity one"],
        )
        stage = GapAnalysisStage()

        with patch(STRUCTURED_TARGET, _structured_mock(gap_result)):
            result = await stage.run(ctx, synthesis)

        assert isinstance(result.output, GapAnalysisResult)
        assert ctx.get_artifact("gap_analysis") == gap_result

    @pytest.mark.asyncio
    async def test_pipeline_includes_synthesis_and_gap_stages(self) -> None:
        ranked = [_ranked("Pipeline Paper", abstract="Content.", year=2024)]
        clusters = [PaperCluster(theme="Theme", summary="Summary", paper_ids=["Pipeline Paper"])]

        class ClusteringStub:
            name = "clustering"

            async def run(self, ctx: PipelineContext, data: object) -> object:
                from src.core.context import StageResult

                ctx.set_artifact("ranked_papers", ranked)
                ctx.set_artifact("paper_clusters", clusters)
                return StageResult(output=clusters, duration_ms=1.0)

        extraction = PaperExtraction(paper_id="Pipeline Paper", title="Pipeline Paper", findings=["F"])
        synthesis = SynthesisResult(agreements=["A"], gaps=["G"])
        gap_result = GapAnalysisResult(gaps=["G"], opportunities=["O"])

        by_type = {
            PaperExtraction: extraction,
            SynthesisResult: synthesis,
            GapAnalysisResult: gap_result,
        }

        async def fake_structured(role, prompt, output_type, llm_config=None, **kwargs):
            return by_type[output_type]

        pipeline = ResearchPipeline(
            [
                ClusteringStub(),
                SynthesisStage(),
                GapAnalysisStage(),
            ],
            AppSettings(
                pipeline={
                    "enabled_stages": {
                        "clustering": True,
                        "synthesis": True,
                        "gap_analysis": True,
                    }
                }
            ),
        )

        with patch(STRUCTURED_TARGET, AsyncMock(side_effect=fake_structured)):
            result = await pipeline.execute("pipeline query")

        assert "synthesis" in result.stage_results
        assert "gap_analysis" in result.stage_results
        assert isinstance(result.output, GapAnalysisResult)


class TestStageRecovery:
    @pytest.mark.asyncio
    async def test_gap_analysis_accepts_cluster_list_after_synthesis_timeout(self) -> None:
        clusters = [PaperCluster(theme="Attention", summary="Summary", paper_ids=["p1"])]
        ranked = [_ranked("Attention Paper", abstract="Self-attention for transformers.", year=2023)]
        ctx = PipelineContext.create("transformer attention", AppSettings())
        ctx.set_artifact("ranked_papers", ranked)
        ctx.set_artifact("paper_clusters", clusters)

        stage = GapAnalysisStage()
        with patch(STRUCTURED_TARGET, _structured_mock(None)):
            result = await stage.run(ctx, clusters)

        assert isinstance(result.output, GapAnalysisResult)
        assert result.output.gaps
        assert ctx.get_artifact("gap_analysis") is not None

    def test_recover_synthesis_output_builds_artifacts(self) -> None:
        clusters = [PaperCluster(theme="Theme", summary="Summary", paper_ids=["Paper A"])]
        ranked = [_ranked("Paper A", abstract="Uses attention.", year=2022)]
        ctx = PipelineContext.create("attention", AppSettings())
        ctx.set_artifact("ranked_papers", ranked)

        synthesis = recover_synthesis_output(ctx, clusters)

        assert isinstance(synthesis, SynthesisResult)
        assert ctx.get_artifact("paper_analyses")
        assert ctx.get_artifact("synthesis_result") == synthesis

    def test_recover_stage_output_after_synthesis_timeout(self) -> None:
        clusters = [PaperCluster(theme="Theme", summary="Summary", paper_ids=["Paper B"])]
        ranked = [_ranked("Paper B", abstract="Benchmark results.", year=2021)]
        ctx = PipelineContext.create("benchmarks", AppSettings())
        ctx.set_artifact("ranked_papers", ranked)

        output = recover_stage_output("synthesis", ctx, clusters)

        assert isinstance(output, SynthesisResult)
        assert ctx.get_artifact("paper_analyses")

    @pytest.mark.asyncio
    async def test_extract_papers_limits_llm_calls(self) -> None:
        ranked = [_ranked(f"Paper {index}", abstract=f"Abstract {index}") for index in range(12)]
        structured = _structured_mock(
            PaperExtraction(
                paper_id="x",
                title="Paper",
                methodology=["m"],
                datasets=["d"],
                benchmarks=[],
                limitations=[],
                findings=["f"],
            )
        )

        settings = AppSettings(
            synthesis={
                "llm_enabled": True,
                "max_llm_papers": 3,
                "concurrency": 2,
            },
        )

        with patch(STRUCTURED_TARGET, structured):
            extractions = await extract_papers(
                ranked,
                "query",
                synthesis_config=settings.synthesis,
            )

        assert len(extractions) == 12
        assert structured.await_count == 3

    @pytest.mark.asyncio
    async def test_extract_papers_skips_llm_when_disabled(self) -> None:
        ranked = [_ranked(f"Paper {index}") for index in range(5)]
        structured = _structured_mock(
            PaperExtraction(
                paper_id="x",
                title="Paper",
                methodology=["m"],
                datasets=["d"],
                benchmarks=[],
                limitations=[],
                findings=["f"],
            )
        )

        with patch(STRUCTURED_TARGET, structured):
            extractions = await extract_papers(
                ranked,
                "query",
                synthesis_config=AppSettings(synthesis={"llm_enabled": False}).synthesis,
            )

        assert len(extractions) == 5
        assert structured.await_count == 0
