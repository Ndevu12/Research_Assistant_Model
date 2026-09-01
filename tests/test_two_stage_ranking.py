# -*- coding: utf-8 -*-
"""Tests for BM25 lexical scoring and cross-encoder reranking."""

from __future__ import annotations

import pytest

from src.config.settings import AppSettings
from src.core.context import PipelineContext
from src.research.bm25 import BM25Corpus, normalized_bm25_scores, tokenize
from src.research.ranking import rank_papers
from src.research.reranker import RerankStage, _min_max_normalize
from src.retrieval.models import RankedPaper, RetrievedPaper


def _paper(title: str, abstract: str = "") -> RetrievedPaper:
    return RetrievedPaper(title=title, abstract=abstract or None, provider="test")


def _ranked(title: str, score: float) -> RankedPaper:
    return RankedPaper(
        paper=_paper(title, abstract=f"About {title}."),
        rank_score=score,
        score_breakdown={},
    )


class TestBM25:
    def test_tokenize_lowercases_words(self) -> None:
        assert tokenize("Graph Neural-Networks!") == ["graph", "neural", "networks"]

    def test_matching_document_outranks_unrelated(self) -> None:
        documents = [
            "graph neural networks for node classification on citation graphs",
            "a study of protein folding in yeast cells",
        ]
        scores = normalized_bm25_scores("graph neural networks", documents)
        assert scores[0] == pytest.approx(1.0)
        assert scores[1] < scores[0]

    def test_rare_terms_earn_more_than_common_terms(self) -> None:
        corpus = BM25Corpus(
            [
                "attention model for translation",
                "attention model for vision",
                "flash attention kernel optimization model",
            ]
        )
        # "flash" appears in one document; "attention" in all three.
        flash_scores = corpus.scores("flash")
        attention_scores = corpus.scores("attention")
        assert max(flash_scores) > max(attention_scores)

    def test_empty_corpus_and_no_overlap(self) -> None:
        assert normalized_bm25_scores("query", []) == []
        assert normalized_bm25_scores("zebra", ["completely unrelated text"]) == [0.0]


class TestRankingWithBM25:
    def test_ranking_records_lexical_bm25_signal(self) -> None:
        papers = [
            _paper(
                "Graph Attention Networks",
                "Masked self-attention over graph neighborhoods for node classification.",
            ),
            _paper("Protein Folding", "A study of protein structures."),
        ]
        settings = AppSettings()

        result = rank_papers(papers, "graph attention networks", config=settings.ranking)

        top = result.ranked[0]
        assert top.paper.title == "Graph Attention Networks"
        assert "lexical_bm25" in top.score_breakdown
        assert top.score_breakdown["lexical_bm25"] == pytest.approx(1.0)


class FakeScorer:
    """Deterministic scorer: prefers documents containing a marker term."""

    model_name = "fake-cross-encoder"

    def __init__(self, marker: str) -> None:
        self.marker = marker
        self.calls: list[tuple[str, int]] = []

    def score(self, query: str, documents: list[str]) -> list[float]:
        self.calls.append((query, len(documents)))
        return [10.0 if self.marker in document.lower() else 1.0 for document in documents]


class TestRerankStage:
    async def test_reranks_top_papers_by_cross_encoder_score(self) -> None:
        settings = AppSettings(rerank={"enabled": True, "top_n": 3, "blend_weight": 0.8})
        ctx = PipelineContext.create("flash attention", settings)
        ranked = [
            _ranked("Unrelated Survey", 0.9),
            _ranked("FlashAttention Kernel", 0.5),
            _ranked("Another Paper", 0.4),
        ]
        scorer = FakeScorer(marker="flashattention")

        result = await RerankStage(scorer=scorer).run(ctx, ranked)

        assert result.output[0].paper.title == "FlashAttention Kernel"
        breakdown = result.output[0].score_breakdown
        assert breakdown["cross_encoder_score"] == pytest.approx(1.0)
        assert breakdown["pre_rerank_score"] == pytest.approx(0.5)
        assert result.metrics["papers_reranked"] == 3
        assert scorer.calls == [("flash attention", 3)]
        assert ctx.get_artifact("ranked_papers") == result.output

    async def test_papers_beyond_top_n_keep_their_order(self) -> None:
        settings = AppSettings(rerank={"enabled": True, "top_n": 2})
        ctx = PipelineContext.create("query", settings)
        ranked = [_ranked("A", 0.9), _ranked("B", 0.8), _ranked("C", 0.7), _ranked("D", 0.6)]

        result = await RerankStage(scorer=FakeScorer(marker="a")).run(ctx, ranked)

        assert [item.paper.title for item in result.output[2:]] == ["C", "D"]

    async def test_passthrough_when_disabled(self) -> None:
        settings = AppSettings(rerank={"enabled": False})
        ctx = PipelineContext.create("query", settings)
        ranked = [_ranked("A", 0.9), _ranked("B", 0.8)]

        result = await RerankStage(scorer=FakeScorer(marker="b")).run(ctx, ranked)

        assert result.output == ranked
        assert result.metrics["papers_reranked"] == 0

    async def test_passthrough_when_backend_missing(self) -> None:
        settings = AppSettings(rerank={"enabled": True})
        ctx = PipelineContext.create("query", settings)
        ranked = [_ranked("A", 0.9), _ranked("B", 0.8)]

        from unittest.mock import patch

        with patch("src.research.reranker.try_create_reranker", return_value=None):
            result = await RerankStage().run(ctx, ranked)

        assert result.output == ranked
        assert any("sentence-transformers" in warning for warning in result.warnings)

    async def test_passthrough_when_scorer_raises(self) -> None:
        settings = AppSettings(rerank={"enabled": True})
        ctx = PipelineContext.create("query", settings)
        ranked = [_ranked("A", 0.9), _ranked("B", 0.8)]

        class FailingScorer:
            def score(self, query: str, documents: list[str]) -> list[float]:
                raise RuntimeError("model load failed")

        result = await RerankStage(scorer=FailingScorer()).run(ctx, ranked)

        assert result.output == ranked
        assert any("reranking failed" in warning.lower() for warning in result.warnings)


def test_min_max_normalize_handles_constant_scores() -> None:
    assert _min_max_normalize([3.0, 3.0]) == [0.5, 0.5]
    assert _min_max_normalize([1.0, 3.0]) == [0.0, 1.0]
