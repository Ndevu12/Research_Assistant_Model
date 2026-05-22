# -*- coding: utf-8 -*-
"""Tests for expanded retrieval domain models."""

from src.retrieval.models import (
    EnhancedResearchReport,
    ExpandedQuerySet,
    PaperAnalysis,
    PaperCluster,
    QueryUnderstandingResult,
    RankedPaper,
    ResearchReport,
    RetrievedPaper,
    SynthesisResult,
)


class TestRetrievedPaper:
    def test_accepts_legacy_source_kwarg(self) -> None:
        paper = RetrievedPaper(
            title="Test Paper",
            abstract="An abstract.",
            year=2024,
            venue="NeurIPS",
            url="https://example.com/paper",
            doi="10.1000/test",
            source="openalex",
        )

        assert paper.provider == "openalex"
        assert paper.source == "openalex"
        assert paper.authors == []
        assert paper.keywords == []
        assert paper.raw_metadata == {}

    def test_accepts_provider_kwarg(self) -> None:
        paper = RetrievedPaper(title="Paper", provider="semantic_scholar")

        assert paper.provider == "semantic_scholar"

    def test_paper_id_prefers_doi(self) -> None:
        paper = RetrievedPaper(
            title="Title",
            doi="10.1000/doi",
            url="https://example.com",
            provider="openalex",
        )

        assert paper.paper_id == "10.1000/doi"


class TestPipelineModels:
    def test_query_understanding_defaults(self) -> None:
        result = QueryUnderstandingResult()

        assert result.intent == ""
        assert result.constraints == {}
        assert result.key_concepts == []

    def test_expanded_query_set(self) -> None:
        expanded = ExpandedQuerySet(
            original="transformers in NLP",
            variants=["attention mechanisms NLP", "BERT architecture"],
            sub_questions=["How do transformers compare to RNNs?"],
        )

        assert expanded.original == "transformers in NLP"
        assert len(expanded.variants) == 2

    def test_ranked_paper(self) -> None:
        paper = RetrievedPaper(title="Ranked", provider="openalex")
        ranked = RankedPaper(paper=paper, rank_score=0.87, score_breakdown={"recency": 0.9})

        assert ranked.rank_score == 0.87
        assert ranked.score_breakdown["recency"] == 0.9

    def test_paper_cluster(self) -> None:
        cluster = PaperCluster(
            theme="Efficiency",
            summary="Papers on model compression.",
            paper_ids=["10.1000/a", "10.1000/b"],
        )

        assert cluster.theme == "Efficiency"
        assert len(cluster.paper_ids) == 2

    def test_synthesis_result(self) -> None:
        synthesis = SynthesisResult(
            agreements=["Transformers dominate"],
            gaps=["Limited multilingual evaluation"],
        )

        assert synthesis.agreements == ["Transformers dominate"]
        assert synthesis.gaps == ["Limited multilingual evaluation"]


class TestEnhancedResearchReport:
    def test_to_research_report_adapter(self) -> None:
        papers = [
            PaperAnalysis(
                title="Paper A",
                key_points=["Point 1"],
                why_relevant=["Relevant"],
            )
        ]
        enhanced = EnhancedResearchReport(
            query="test query",
            executive_summary="Summary",
            papers=papers,
            clusters=[PaperCluster(theme="Theme", paper_ids=["id-1"])],
        )

        legacy = enhanced.to_research_report()

        assert isinstance(legacy, ResearchReport)
        assert legacy.query == "test query"
        assert legacy.papers == papers
