# -*- coding: utf-8 -*-
"""Tests for query expansion, ranking, clustering, and deduplication stages."""

from __future__ import annotations

import numpy as np
import pytest

from src.config.settings import (
    AppSettings,
    ClusteringConfig,
    DeduplicationConfig,
    QueryExpansionConfig,
    RankingConfig,
    RankingWeights,
)
from src.core.context import PipelineContext
from src.core.pipeline import ResearchPipeline
from src.embeddings.base import EmbeddingProvider
from src.research.clustering import ClusteringStage, cluster_papers
from src.research.query_expansion import QueryExpansionStage, expand_query_heuristic
from src.research.ranking import RankingStage, rank_papers
from src.retrieval.deduplication import DeduplicationStage, deduplicate_papers
from src.retrieval.models import RankedPaper, RetrievedPaper


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for tests."""

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            seed = sum(ord(char) for char in text)
            vectors.append(
                np.array(
                    [
                        (seed % 7) / 7.0,
                        ((seed // 7) % 11) / 11.0,
                        ((seed // 77) % 13) / 13.0,
                    ],
                    dtype=np.float32,
                )
            )
        return np.vstack(vectors)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        if a_norm == 0.0 or b_norm == 0.0:
            return 0.0
        return float(np.dot(a, b) / (a_norm * b_norm))


class FixedEmbeddingProvider(EmbeddingProvider):
    """Provider with explicit vectors for deduplication tests."""

    def __init__(self, vectors: list[np.ndarray]) -> None:
        self._vectors = vectors

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if len(texts) != len(self._vectors):
            raise ValueError("Unexpected number of texts")
        return np.vstack(self._vectors)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        if a_norm == 0.0 or b_norm == 0.0:
            return 0.0
        return float(np.dot(a, b) / (a_norm * b_norm))


def _paper(
    title: str,
    *,
    abstract: str | None = None,
    year: int | None = None,
    venue: str | None = None,
    doi: str | None = None,
    citation_count: int | None = None,
    authors: list[str] | None = None,
) -> RetrievedPaper:
    return RetrievedPaper(
        title=title,
        abstract=abstract,
        year=year,
        venue=venue,
        doi=doi,
        citation_count=citation_count,
        authors=authors or [],
        provider="openalex",
    )


class TestQueryExpansion:
    def test_heuristic_expansion_for_nlp_query(self) -> None:
        expanded = expand_query_heuristic("recent NLP transformer models")

        assert expanded.original == "recent NLP transformer models"
        assert any("natural language processing" in variant.lower() for variant in expanded.variants)
        assert len(expanded.sub_questions) >= 2

    def test_heuristic_expansion_is_stable(self) -> None:
        first = expand_query_heuristic("machine learning for computer vision")
        second = expand_query_heuristic("machine learning for computer vision")

        assert first.variants == second.variants
        assert first.sub_questions == second.sub_questions

    @pytest.mark.asyncio
    async def test_query_expansion_stage(self) -> None:
        stage = QueryExpansionStage()
        ctx = PipelineContext.create("transformer attention", AppSettings())
        result = await stage.run(ctx, "transformer attention")

        assert result.output.original == "transformer attention"
        assert len(result.output.variants) > 0
        assert result.metrics["variant_count"] == len(result.output.variants)


class TestRanking:
    def test_ranks_more_relevant_and_recent_papers_higher(self) -> None:
        papers = [
            _paper(
                "Unrelated biology survey",
                abstract="Cell structures and proteins.",
                year=2010,
                citation_count=10,
            ),
            _paper(
                "Transformer models for natural language processing",
                abstract="Attention-based transformer architectures for NLP tasks.",
                year=2024,
                venue="NeurIPS",
                citation_count=500,
                authors=["A", "B", "C", "D"],
            ),
            _paper(
                "Generic methods paper",
                abstract="Various techniques.",
                year=2018,
                citation_count=50,
            ),
        ]

        ranked = rank_papers(
            papers,
            "transformer NLP",
            config=RankingConfig(top_k=3),
            embedder=None,
        )

        assert ranked[0].paper.title.startswith("Transformer models")
        assert ranked[0].rank_score >= ranked[1].rank_score >= ranked[2].rank_score
        assert ranked[0].paper.title == "Transformer models for natural language processing"
        assert ranked[-1].paper.title == "Unrelated biology survey"

    def test_ranking_order_is_deterministic_for_fixed_fixtures(self) -> None:
        papers = [
            _paper("Third place", abstract="Unrelated topic.", year=2010, citation_count=5),
            _paper("First place transformers", abstract="Transformers and NLP.", year=2024, citation_count=200),
            _paper("Second place transformers", abstract="Transformer models.", year=2020, citation_count=80),
        ]

        ranked = rank_papers(
            papers,
            "transformers NLP",
            config=RankingConfig(top_k=3),
            embedder=None,
        )
        titles = [item.paper.title for item in ranked]

        assert titles == [
            "First place transformers",
            "Second place transformers",
            "Third place",
        ]

    def test_redistributes_weights_when_citations_missing(self) -> None:
        papers = [
            _paper(
                "Transformers in NLP",
                abstract="Transformers and attention for language modeling.",
                year=2023,
            )
        ]
        weights = RankingWeights(citation_count=0.5, semantic_relevance=0.5)

        ranked = rank_papers(
            papers,
            "transformers NLP",
            config=RankingConfig(top_k=1, weights=weights),
        )

        assert "citation_count" not in ranked[0].score_breakdown
        assert ranked[0].rank_score > 0.0

    @pytest.mark.asyncio
    async def test_ranking_stage_records_top_score(self) -> None:
        papers = [
            _paper("Transformers in NLP", abstract="Attention models.", year=2024),
            _paper("Other topic", abstract="Unrelated.", year=2010),
        ]
        stage = RankingStage(embedder=MockEmbeddingProvider())
        ctx = PipelineContext.create("transformers NLP", AppSettings())

        result = await stage.run(ctx, papers)

        assert len(result.output) == 2
        assert result.metrics["top_score"] == result.output[0].rank_score
        assert ctx.metrics.ranking_top_score == result.output[0].rank_score


class TestClustering:
    def test_synthetic_embeddings_produce_expected_cluster_count(self) -> None:
        """Two well-separated embedding groups should yield two clusters."""
        group_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        group_b = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        embedder = FixedEmbeddingProvider(
            [
                group_a,
                group_a + np.array([0.01, 0.0, 0.0], dtype=np.float32),
                group_b,
                group_b + np.array([0.0, 0.01, 0.0], dtype=np.float32),
            ]
        )
        ranked = [
            RankedPaper(paper=_paper("Alpha transformer study"), rank_score=0.9),
            RankedPaper(paper=_paper("Alpha transformer replication"), rank_score=0.85),
            RankedPaper(paper=_paper("Beta biology dataset"), rank_score=0.8),
            RankedPaper(paper=_paper("Beta biology benchmark"), rank_score=0.75),
        ]

        clusters = cluster_papers(
            ranked,
            config=ClusteringConfig(min_cluster_size=2, min_samples=1),
            embedder=embedder,
        )

        assert len(clusters) == 2
        cluster_sizes = sorted(len(cluster.paper_ids) for cluster in clusters)
        assert cluster_sizes == [2, 2]

    def test_clusters_similar_embeddings_together(self) -> None:
        embedder = MockEmbeddingProvider()
        ranked = [
            RankedPaper(paper=_paper("Alpha transformer study"), rank_score=0.9),
            RankedPaper(paper=_paper("Alpha transformer study replication"), rank_score=0.8),
            RankedPaper(paper=_paper("Beta biology dataset"), rank_score=0.7),
            RankedPaper(paper=_paper("Beta biology benchmark"), rank_score=0.6),
        ]

        clusters = cluster_papers(
            ranked,
            config=ClusteringConfig(min_cluster_size=2, min_samples=1),
            embedder=embedder,
        )

        assert len(clusters) >= 1
        assert all(cluster.paper_ids for cluster in clusters)

    def test_single_paper_returns_one_cluster(self) -> None:
        ranked = [RankedPaper(paper=_paper("Only paper"), rank_score=1.0)]

        clusters = cluster_papers(
            ranked,
            embedder=MockEmbeddingProvider(),
        )

        assert len(clusters) == 1
        assert clusters[0].paper_ids == ["Only paper"]

    @pytest.mark.asyncio
    async def test_clustering_stage_records_metrics(self) -> None:
        ranked = [
            RankedPaper(paper=_paper("Topic A paper 1"), rank_score=0.9),
            RankedPaper(paper=_paper("Topic A paper 2"), rank_score=0.8),
        ]
        stage = ClusteringStage(embedder=MockEmbeddingProvider())
        ctx = PipelineContext.create("topic a", AppSettings())

        result = await stage.run(ctx, ranked)

        assert len(result.output) >= 1
        assert ctx.metrics.clustering_num_clusters == len(result.output)


class TestDeduplication:
    def test_metadata_dedup_removes_same_doi(self) -> None:
        papers = [
            _paper("Paper A", doi="10.1000/a"),
            _paper("Paper A duplicate", doi="10.1000/a"),
            _paper("Paper B", doi="10.1000/b"),
        ]

        deduped, stats = deduplicate_papers(
            papers,
            config=DeduplicationConfig(enable_embedding_dedup=False),
        )

        assert len(deduped) == 2
        assert stats["metadata_removed"] == 1

    def test_embedding_dedup_removes_near_duplicates(self) -> None:
        papers = [
            _paper("Transformer alpha study", abstract="Attention is all you need."),
            _paper("Transformer beta study", abstract="Attention is all you need."),
            _paper("Biology of cells", abstract="Completely different domain."),
        ]
        near_duplicate = np.array([1.0, 0.0], dtype=np.float32)
        distinct = np.array([0.0, 1.0], dtype=np.float32)
        embedder = FixedEmbeddingProvider([near_duplicate, near_duplicate, distinct])

        deduped, stats = deduplicate_papers(
            papers,
            config=DeduplicationConfig(
                enable_embedding_dedup=True,
                embedding_similarity_threshold=0.99,
            ),
            embedder=embedder,
        )

        assert len(deduped) == 2
        assert stats["embedding_removed"] == 1

    @pytest.mark.asyncio
    async def test_deduplication_stage(self) -> None:
        papers = [
            _paper("Same title", doi="10.1/a"),
            _paper("Same title", doi="10.1/a"),
        ]
        stage = DeduplicationStage()
        ctx = PipelineContext.create("query", AppSettings())

        result = await stage.run(ctx, papers)

        assert len(result.output) == 1
        assert result.metrics["metadata_removed"] == 1


class TestResearchPipelineStages:
    @pytest.mark.asyncio
    async def test_pipeline_runs_research_stages_in_order(self) -> None:
        embedder = MockEmbeddingProvider()
        papers = [
            _paper(
                "Transformers for NLP",
                abstract="Attention-based language models.",
                year=2024,
                citation_count=100,
            ),
            _paper(
                "Transformers for NLP",
                doi="10.1000/dup",
                abstract="Attention-based language models.",
                year=2024,
                citation_count=100,
            ),
            _paper("Unrelated biology", abstract="Cells and proteins.", year=2010),
        ]

        class RetrievalStub:
            name = "retrieval"

            async def run(self, ctx: PipelineContext, data: object) -> object:
                from src.core.context import StageResult

                return StageResult(output=papers, duration_ms=1.0)

        pipeline = ResearchPipeline(
            [
                QueryExpansionStage(),
                RetrievalStub(),
                DeduplicationStage(embedder=embedder),
                RankingStage(embedder=embedder),
                ClusteringStage(embedder=embedder),
            ],
            AppSettings(
                pipeline={
                    "enabled_stages": {
                        "query_expansion": True,
                        "retrieval": True,
                        "deduplication": True,
                        "ranking": True,
                        "clustering": True,
                    }
                }
            ),
        )

        result = await pipeline.execute("transformers NLP")

        assert "query_expansion" in result.stage_results
        assert "deduplication" in result.stage_results
        assert "ranking" in result.stage_results
        assert "clustering" in result.stage_results
        assert isinstance(result.output, list)
        assert all(hasattr(cluster, "theme") for cluster in result.output)
