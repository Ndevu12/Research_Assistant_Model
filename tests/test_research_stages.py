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
    RelevanceScoringConfig,
)
from src.core.context import PipelineContext
from src.core.pipeline import ResearchPipeline
from src.embeddings.base import EmbeddingProvider
from src.research.clustering import (
    ClusteringStage,
    _merge_noise_into_macro_clusters,
    cluster_papers,
)
from src.research.embedding_context import (
    PAPER_EMBEDDINGS_KEY,
    QUERY_EMBEDDING_KEY,
    get_paper_embeddings,
    get_query_embedding,
)
from src.research.query_expansion import (
    QueryExpansionStage,
    expand_query_heuristic,
)
from src.research.canonical_works import load_canonical_works
from src.research.metadata_sanity import (
    check_doi_prefix_mismatch,
    check_suspicious_year,
    sanitize_paper_metadata,
)
from src.research.ranking import (
    RankingStage,
    embedding_outlier,
    keyword_collision,
    rank_papers,
)
from src.research.relevance_scoring import (
    RelevanceScoringStage,
    compute_adaptive_embedding_floor,
)
from src.retrieval.deduplication import DeduplicationStage, dedupe_by_metadata, deduplicate_papers
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
        self.embed_calls = 0

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        self.embed_calls += 1
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
        ).ranked

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
        ).ranked
        titles = [item.paper.title for item in ranked]

        assert titles == [
            "First place transformers",
            "Second place transformers",
            "Third place",
        ]

    def test_embedding_outlier_penalty(self) -> None:
        assert embedding_outlier(0.2, 0.8, 0.12) is True
        assert embedding_outlier(0.75, 0.8, 0.12) is False
        assert embedding_outlier(None, 0.8, 0.12) is False
        assert embedding_outlier(0.2, None, 0.12) is False

    def test_keyword_collision_penalty(self) -> None:
        paper = _paper(
            "Transformer attention in pollution monitoring",
            abstract="Air pollution study using transformer attention naming collision.",
        )
        query_terms = {"transformer", "attention", "mechanisms"}
        assert keyword_collision(paper, query_terms, 0.3, 0.40) is True
        assert keyword_collision(paper, query_terms, 0.5, 0.40) is False
        assert keyword_collision(paper, query_terms, None, 0.40) is False

    def test_ranking_canonical_boost(self) -> None:
        papers = [
            _paper(
                "Attention Is All You Need",
                abstract="The dominant sequence transduction models are based on self-attention.",
                year=2017,
                citation_count=100,
            ),
            _paper(
                "Generic attention survey",
                abstract="Attention mechanisms in various domains.",
                year=2017,
                citation_count=100,
            ),
        ]

        ranked = rank_papers(
            papers,
            "transformer attention",
            config=RankingConfig(top_k=2, canonical_boost=0.05),
            embedder=None,
        ).ranked

        canonical = next(item for item in ranked if "Attention Is All You Need" in item.paper.title)
        generic = next(item for item in ranked if item.paper.title == "Generic attention survey")

        assert "canonical_boost" in canonical.score_breakdown
        assert canonical.rank_score > generic.rank_score

    def test_semantic_relevance_uses_embeddings_when_available(self) -> None:
        papers = [
            _paper("On-topic transformers", abstract="Transformers and NLP.", year=2024),
            _paper("Off-topic biology", abstract="Cell structures.", year=2024),
        ]
        embedder = FixedEmbeddingProvider(
            [
                np.array([1.0, 0.0, 0.0], dtype=np.float32),
                np.array([0.99, 0.01, 0.0], dtype=np.float32),
                np.array([0.0, 1.0, 0.0], dtype=np.float32),
            ]
        )

        ranked = rank_papers(
            papers,
            "transformers NLP",
            config=RankingConfig(top_k=2),
            embedder=embedder,
        ).ranked

        on_topic = ranked[0]
        assert on_topic.paper.title == "On-topic transformers"
        assert on_topic.score_breakdown["semantic_relevance"] > 0.9

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
        ).ranked

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

    @pytest.mark.asyncio
    async def test_ranking_stage_stores_embedding_artifacts(self) -> None:
        papers = [
            _paper("Transformers in NLP", abstract="Attention models.", year=2024),
            _paper("Other topic", abstract="Unrelated.", year=2010),
        ]
        stage = RankingStage(embedder=MockEmbeddingProvider())
        ctx = PipelineContext.create("transformers NLP", AppSettings())

        await stage.run(ctx, papers)

        query_embedding = get_query_embedding(ctx)
        paper_embeddings = get_paper_embeddings(ctx)

        assert query_embedding is not None
        assert len(paper_embeddings) == 2
        assert all(paper.paper_id in paper_embeddings for paper in papers)
        assert ctx.get_artifact(QUERY_EMBEDDING_KEY) is not None
        assert ctx.get_artifact(PAPER_EMBEDDINGS_KEY) is not None


class TestRelevanceScoring:
    @pytest.mark.asyncio
    async def test_relevance_reuses_cached_embeddings(self) -> None:
        papers = [
            _paper("Transformers in NLP", abstract="Attention models.", year=2024),
            _paper("Other topic", abstract="Unrelated.", year=2010),
        ]
        ranking_stage = RankingStage(embedder=MockEmbeddingProvider())
        relevance_stage = RelevanceScoringStage()
        ctx = PipelineContext.create("transformers NLP", AppSettings())

        ranked_result = await ranking_stage.run(ctx, papers)
        relevance_result = await relevance_stage.run(ctx, ranked_result.output)

        assert all(
            "embedding_similarity" in paper.score_breakdown
            for paper in relevance_result.output
        )

    @pytest.mark.asyncio
    async def test_relevance_keeps_min_papers_floor(self) -> None:
        query = "transformer attention mechanisms"
        passing = RankedPaper(
            paper=_paper(
                "Self-Attention Transformers for NLP",
                abstract="Transformer attention mechanisms in language models.",
                year=2024,
            ),
            rank_score=0.8,
        )
        failing = [
            RankedPaper(
                paper=_paper(
                    f"Borderline paper {index}",
                    abstract="Only partial transformer mention.",
                    year=2024,
                ),
                rank_score=0.1 + (index * 0.01),
            )
            for index in range(3)
        ]
        papers = failing + [passing]
        settings = AppSettings(
            relevance_scoring=RelevanceScoringConfig(
                min_rank_score=0.5,
                min_embedding_similarity=0.9,
                require_all_concepts=True,
                min_papers=3,
            )
        )
        ctx = PipelineContext.create(query, settings)
        relevance_stage = RelevanceScoringStage()
        result = await relevance_stage.run(ctx, papers)

        assert len(result.output) == 3
        assert any("Raised relevance floor" in warning for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_relevance_records_filter_reasons(self) -> None:
        query = "transformer attention mechanisms"
        off_topic = _paper(
            "Air pollutant transformer protein",
            abstract="Environmental pollution study.",
            year=2025,
        )
        settings = AppSettings(
            relevance_scoring=RelevanceScoringConfig(
                min_rank_score=0.25,
                min_embedding_similarity=0.35,
                require_all_concepts=True,
                min_papers=1,
            )
        )
        ctx = PipelineContext.create(query, settings)
        ctx.set_artifact(QUERY_EMBEDDING_KEY, np.array([1.0, 0.0, 0.0], dtype=np.float32))
        ctx.set_artifact(
            PAPER_EMBEDDINGS_KEY,
            {off_topic.paper_id: np.array([0.0, 1.0, 0.0], dtype=np.float32)},
        )

        ranked = [RankedPaper(paper=off_topic, rank_score=0.9)]
        relevance_stage = RelevanceScoringStage()
        await relevance_stage.run(ctx, ranked)

        reasons = ctx.get_artifact("relevance_filter_reasons")
        assert isinstance(reasons, dict)
        assert off_topic.paper_id in reasons

    def test_compute_adaptive_embedding_floor_uses_gap_from_top(self) -> None:
        config = RelevanceScoringConfig(
            min_embedding_similarity=0.35,
            keep_percentile=25.0,
            gap_from_top=0.12,
        )
        similarities = [0.52, 0.50, 0.48, 0.46, 0.44, 0.36]

        floor = compute_adaptive_embedding_floor(
            similarities,
            config=config,
            corpus_size=len(similarities),
        )

        assert floor == pytest.approx(0.40)

    def test_compute_adaptive_embedding_floor_skips_percentile_for_small_corpus(self) -> None:
        config = RelevanceScoringConfig(
            min_embedding_similarity=0.35,
            keep_percentile=25.0,
            gap_from_top=0.12,
        )
        similarities = [0.52, 0.50, 0.48, 0.36]

        floor = compute_adaptive_embedding_floor(
            similarities,
            config=config,
            corpus_size=len(similarities),
        )

        assert floor == pytest.approx(0.40)

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

    def test_merge_noise_into_macro_themes(self) -> None:
        noise_papers = [
            RankedPaper(
                paper=_paper(
                    "Transformer attention for language modeling",
                    abstract="Self-attention mechanisms in neural networks.",
                ),
                rank_score=0.9,
            ),
            RankedPaper(
                paper=_paper(
                    "Vision transformer image classification",
                    abstract="Attention-based vision models for images.",
                ),
                rank_score=0.85,
            ),
            RankedPaper(
                paper=_paper(
                    "Air pollutant transformer protein binding",
                    abstract="Environmental pollution and protein interactions.",
                ),
                rank_score=0.8,
            ),
            RankedPaper(
                paper=_paper(
                    "Cervical cancer attention screening model",
                    abstract="Medical imaging with attention networks.",
                ),
                rank_score=0.75,
            ),
        ]

        clusters = _merge_noise_into_macro_clusters(
            noise_papers,
            ClusteringConfig(max_macro_clusters=4),
        )

        assert 1 <= len(clusters) <= 4
        assert all(cluster.theme.startswith("Theme:") for cluster in clusters)
        assert not any("Unclustered:" in cluster.theme for cluster in clusters)
        merged_ids = {paper_id for cluster in clusters for paper_id in cluster.paper_ids}
        assert merged_ids == {paper.paper.paper_id for paper in noise_papers}

    def test_clustering_merges_high_noise_into_macro_themes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ranked = [
            RankedPaper(
                paper=_paper("Transformer attention language model"),
                rank_score=0.9,
            ),
            RankedPaper(
                paper=_paper("Vision transformer image recognition"),
                rank_score=0.85,
            ),
            RankedPaper(
                paper=_paper("Air pollutant protein transformer study"),
                rank_score=0.8,
            ),
            RankedPaper(
                paper=_paper("Medical attention screening network"),
                rank_score=0.75,
            ),
            RankedPaper(
                paper=_paper("Scaled dot-product attention survey"),
                rank_score=0.7,
            ),
            RankedPaper(
                paper=_paper("Polarimetric remote sensing transformer"),
                rank_score=0.65,
            ),
        ]
        monkeypatch.setattr(
            "src.research.clustering._cluster_with_hdbscan",
            lambda _embeddings, _config: np.full(len(ranked), -1, dtype=int),
        )

        clusters = cluster_papers(
            ranked,
            config=ClusteringConfig(
                min_cluster_size=2,
                min_samples=1,
                noise_merge_threshold=0.5,
                max_macro_clusters=4,
            ),
            embedder=MockEmbeddingProvider(),
        )

        assert 1 <= len(clusters) <= 4
        assert all(cluster.theme.startswith("Theme:") for cluster in clusters)
        assert not any("Unclustered:" in cluster.theme for cluster in clusters)

    def test_clustering_keeps_unclustered_singletons_when_noise_low(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ranked = [
            RankedPaper(paper=_paper("Alpha transformer study"), rank_score=0.9),
            RankedPaper(paper=_paper("Alpha transformer replication"), rank_score=0.85),
            RankedPaper(paper=_paper("Unrelated singleton paper"), rank_score=0.8),
        ]
        monkeypatch.setattr(
            "src.research.clustering._cluster_with_hdbscan",
            lambda _embeddings, _config: np.array([0, 0, -1], dtype=int),
        )

        clusters = cluster_papers(
            ranked,
            config=ClusteringConfig(
                min_cluster_size=2,
                min_samples=1,
                noise_merge_threshold=0.5,
            ),
            embedder=MockEmbeddingProvider(),
        )

        assert any("Unclustered:" in cluster.theme for cluster in clusters)
        assert sum(len(cluster.paper_ids) for cluster in clusters) == len(ranked)

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

    @pytest.mark.asyncio
    async def test_clustering_stage_reuses_cached_embeddings(self) -> None:
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
        ctx = PipelineContext.create("transformers", AppSettings())
        ctx.set_artifact(
            PAPER_EMBEDDINGS_KEY,
            {
                ranked[0].paper.paper_id: group_a,
                ranked[1].paper.paper_id: group_a + np.array([0.01, 0.0, 0.0], dtype=np.float32),
                ranked[2].paper.paper_id: group_b,
                ranked[3].paper.paper_id: group_b + np.array([0.0, 0.01, 0.0], dtype=np.float32),
            },
        )

        stage = ClusteringStage(embedder=embedder)
        await stage.run(ctx, ranked)

        assert embedder.embed_calls == 0


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

    def test_metadata_dedup_keeps_richer_duplicate(self) -> None:
        papers = [
            _paper("Attention Is All You Need", year=2025, doi="10.65215/bad"),
            _paper(
                "Attention Is All You Need",
                year=2025,
                doi="10.48550/arxiv.1706.03762",
                abstract="The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
                citation_count=5000,
            ),
        ]

        deduped = dedupe_by_metadata(papers)

        assert len(deduped) == 1
        kept = deduped[0]
        assert kept.year == 2025
        assert kept.citation_count == 5000
        assert kept.doi == "10.48550/arxiv.1706.03762"


class TestMetadataSanity:
    def test_sanitize_corrects_canonical_year(self) -> None:
        paper = _paper("Attention Is All You Need", year=2025, doi="10.48550/arxiv.1706.03762")
        works = load_canonical_works()

        corrected = sanitize_paper_metadata(paper, works, current_year=2026)

        assert corrected.year == 2017
        assert "suspicious_year" in corrected.raw_metadata["metadata_sanity_flags"]

    def test_sanitize_flags_doi_prefix_mismatch(self) -> None:
        paper = _paper("Attention Is All You Need", year=2017, doi="10.65215/bad")
        works = load_canonical_works()
        canonical = works[0]

        assert check_doi_prefix_mismatch(paper, canonical) is True

        corrected = sanitize_paper_metadata(paper, works, current_year=2026)

        assert corrected.year == 2017
        assert "doi_prefix_mismatch" in corrected.raw_metadata["metadata_sanity_flags"]

    def test_suspicious_year_for_future_publication(self) -> None:
        paper = _paper("Some future paper", year=2030)

        assert check_suspicious_year(paper, current_year=2026) is True

    def test_suspicious_year_allows_next_calendar_year(self) -> None:
        paper = _paper("Early access paper", year=2027)

        assert check_suspicious_year(paper, current_year=2026) is False

    def test_sanitize_flags_invalid_doi_format(self) -> None:
        paper = _paper("Some paper", year=2024, doi="not-a-doi")

        corrected = sanitize_paper_metadata(paper, current_year=2026)

        assert "invalid_doi_format" in corrected.raw_metadata["metadata_sanity_flags"]

    def test_ranking_applies_metadata_sanity(self) -> None:
        papers = [
            _paper(
                "Some future paper",
                abstract="Self-attention transformer architecture.",
                year=2030,
                doi="10.48550/arxiv.1706.03762",
                citation_count=100,
            ),
        ]

        ranked = rank_papers(
            papers,
            "transformer attention",
            config=RankingConfig(top_k=1),
            embedder=None,
        ).ranked

        assert ranked[0].paper.year == 2030
        assert "future_year" in ranked[0].paper.raw_metadata["metadata_sanity_flags"]


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
