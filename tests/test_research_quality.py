# -*- coding: utf-8 -*-
"""Multi-domain regression tests for research quality logic."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from src.config.settings import (
    AppSettings,
    ClusteringConfig,
    RankingConfig,
    RelevanceScoringConfig,
)
from src.core.context import PipelineContext
from src.reporting.report_generation import _build_executive_summary
from src.research.clustering import cluster_papers
from src.research.embedding_context import PAPER_EMBEDDINGS_KEY, QUERY_EMBEDDING_KEY
from src.research.query_expansion import expand_query_heuristic, extract_core_concepts
from src.research.ranking import rank_papers
from src.research.relevance_scoring import RelevanceScoringStage
from src.retrieval.models import PaperCluster, RankedPaper, RetrievedPaper, SynthesisResult


@dataclass(frozen=True)
class DomainCase:
    """Synthetic fixture for one unrelated research domain."""

    domain: str
    query: str
    on_topic_titles: tuple[str, ...]
    decoy_title: str
    decoy_abstract: str
    decoy_domain_terms: tuple[str, ...]
    broad_single_token_variants: frozenset[str]


DOMAIN_CASES: tuple[DomainCase, ...] = (
    DomainCase(
        domain="nlp",
        query="transformer attention mechanisms",
        on_topic_titles=(
            "Self-Attention Transformers for NLP",
            "Efficient transformer attention for natural language processing",
        ),
        decoy_title="Air pollutant transformer protein interactions",
        decoy_abstract=(
            "Air pollution poses a critical global public health challenge "
            "using transformer naming in environmental chemistry."
        ),
        decoy_domain_terms=("air pollutant", "air pollution"),
        broad_single_token_variants=frozenset(
            {"attention", "transformer", "learning", "model", "models", "network", "networks"}
        ),
    ),
    DomainCase(
        domain="biomedical",
        query="CRISPR gene editing therapy",
        on_topic_titles=(
            "CRISPR-Cas9 gene editing for therapeutic applications",
            "In vivo CRISPR therapy for genetic disorders",
        ),
        decoy_title="Video editing gene expression in film production",
        decoy_abstract=(
            "Digital video editing workflows and gene naming conventions "
            "in cinematic post-production pipelines."
        ),
        decoy_domain_terms=("video editing", "film production", "cinematic"),
        broad_single_token_variants=frozenset({"gene", "editing", "therapy", "crispr"}),
    ),
    DomainCase(
        domain="climate",
        query="carbon capture storage methods",
        on_topic_titles=(
            "Direct air carbon capture and storage feasibility",
            "Geological carbon storage methods for industrial emissions",
        ),
        decoy_title="Image capture storage formats for digital cameras",
        decoy_abstract=(
            "Consumer camera image capture pipelines and storage card "
            "format benchmarks for photography workflows."
        ),
        decoy_domain_terms=("digital cameras", "photography", "image capture"),
        broad_single_token_variants=frozenset({"capture", "storage", "carbon", "methods"}),
    ),
    DomainCase(
        domain="economics",
        query="inflation monetary policy effects",
        on_topic_titles=(
            "Monetary policy transmission and inflation dynamics",
            "Central bank policy effects on consumer price inflation",
        ),
        decoy_title="Insurance policy effects on claims inflation",
        decoy_abstract=(
            "Property insurance policy wording and claims inflation "
            "adjustments in underwriting practice."
        ),
        decoy_domain_terms=("insurance policy", "underwriting", "claims inflation"),
        broad_single_token_variants=frozenset({"policy", "inflation", "effects", "monetary"}),
    ),
)

BANNED_ML_BRANCH_PATTERNS = (
    "_ML_ATTENTION_TEMPLATES",
    "_ml_attention_templates",
    "_ML_DOMAIN_MARKERS",
    "_AMBIGUOUS_QUERY_TERMS",
    "query_is_ml",
)


class FixedEmbeddingProvider:
    """Provider with explicit vectors for quality regression tests."""

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
    citation_count: int | None = None,
) -> RetrievedPaper:
    return RetrievedPaper(
        title=title,
        abstract=abstract,
        year=year,
        citation_count=citation_count,
        provider="openalex",
    )


def _domain_papers(case: DomainCase) -> tuple[list[RetrievedPaper], FixedEmbeddingProvider]:
    on_topic = [
        _paper(
            title,
            abstract=f"{title}. Research aligned with {case.query}.",
            year=2023,
            citation_count=120,
        )
        for title in case.on_topic_titles
    ]
    decoy = _paper(
        case.decoy_title,
        abstract=case.decoy_abstract,
        year=2025,
        citation_count=500,
    )
    papers = [decoy, *on_topic]

    query_vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    decoy_vec = np.array([0.1, 0.9, 0.0], dtype=np.float32)
    on_topic_vecs = [
        np.array([0.95 - (index * 0.02), 0.05, 0.0], dtype=np.float32)
        for index in range(len(on_topic))
    ]
    embedder = FixedEmbeddingProvider([query_vec, decoy_vec, *on_topic_vecs])
    return papers, embedder


@pytest.fixture(params=DOMAIN_CASES, ids=lambda case: case.domain)
def domain_case(request: pytest.FixtureRequest) -> DomainCase:
    return request.param


class TestMultiDomainExpansion:
    def test_expansion_no_degenerate_variants(self, domain_case: DomainCase) -> None:
        expanded = expand_query_heuristic(domain_case.query, max_variants=10)
        key_concepts = extract_core_concepts(domain_case.query)

        for variant in expanded.variants:
            assert variant.lower() != domain_case.query.lower()
            assert "attention mechanism attention" not in variant.lower()
            assert "self-attention attention" not in variant.lower()
            if len(key_concepts) >= 2:
                assert variant.lower() not in domain_case.broad_single_token_variants


class TestMultiDomainRanking:
    def test_ranking_demotes_embedding_outliers(self, domain_case: DomainCase) -> None:
        papers, embedder = _domain_papers(domain_case)

        ranked = rank_papers(
            papers,
            domain_case.query,
            config=RankingConfig(top_k=len(papers), outlier_embedding_gap=0.12),
            embedder=embedder,
        ).ranked

        assert ranked[0].paper.title != domain_case.decoy_title
        decoy = next(item for item in ranked if item.paper.title == domain_case.decoy_title)
        assert decoy.score_breakdown.get("penalty_embedding_outlier") == 1.0


class TestMultiDomainRelevance:
    @pytest.mark.asyncio
    async def test_relevance_adaptive_filter(self, domain_case: DomainCase) -> None:
        papers, embedder = _domain_papers(domain_case)
        decoy, *on_topic = papers

        query_vec = embedder._vectors[0]
        decoy_vec = embedder._vectors[1]
        on_topic_vecs = embedder._vectors[2:]

        settings = AppSettings(
            relevance_scoring=RelevanceScoringConfig(
                min_rank_score=0.25,
                min_embedding_similarity=0.35,
                require_all_concepts=True,
                min_papers=1,
                adaptive_embedding=True,
                gap_from_top=0.12,
            )
        )
        ctx = PipelineContext.create(domain_case.query, settings)
        ctx.set_artifact(QUERY_EMBEDDING_KEY, query_vec)
        ctx.set_artifact(
            PAPER_EMBEDDINGS_KEY,
            {
                decoy.paper_id: decoy_vec,
                **{
                    paper.paper_id: on_topic_vecs[index]
                    for index, paper in enumerate(on_topic)
                },
            },
        )

        ranked = [
            RankedPaper(paper=decoy, rank_score=0.9),
            *[RankedPaper(paper=paper, rank_score=0.8 - (index * 0.05)) for index, paper in enumerate(on_topic)],
        ]
        result = await RelevanceScoringStage().run(ctx, ranked)

        kept_ids = {paper.paper.paper_id for paper in result.output}
        assert decoy.paper_id not in kept_ids
        assert any(paper.paper_id in kept_ids for paper in on_topic)
        assert result.metrics["papers_filtered"] >= 1


class TestMultiDomainExecutiveSummary:
    def test_executive_summary_query_aligned(self, domain_case: DomainCase) -> None:
        clusters = [
            PaperCluster(theme=f"{domain_case.domain.title()} Research Theme", paper_ids=["a"]),
            PaperCluster(theme="Secondary Theme", paper_ids=["b"]),
        ]
        synthesis = SynthesisResult(
            agreements=[f"{domain_case.decoy_abstract} Notable finding snippet."],
        )
        ranked = [
            RankedPaper(
                paper=_paper(domain_case.decoy_title, abstract=domain_case.decoy_abstract),
                rank_score=0.2,
                score_breakdown={"embedding_similarity": 0.1},
            )
        ]

        summary = _build_executive_summary(
            domain_case.query,
            synthesis,
            clusters,
            paper_count=2,
            ranked_papers=ranked,
            relevance_config=RelevanceScoringConfig(min_embedding_similarity=0.35),
        )

        assert domain_case.query in summary
        assert "review of 2 paper(s)" in summary
        for term in domain_case.decoy_domain_terms:
            assert term not in summary.lower()


class TestNoDomainSpecificBranches:
    @pytest.mark.parametrize(
        "module_path",
        [
            "src/research/query_expansion.py",
            "src/research/ranking.py",
        ],
    )
    def test_no_ml_specific_branches(self, module_path: str) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        content = (repo_root / module_path).read_text(encoding="utf-8")
        for pattern in BANNED_ML_BRANCH_PATTERNS:
            assert pattern not in content, f"{pattern} found in {module_path}"


class TestMultiDomainClustering:
    def test_clustering_no_singleton_spam(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ranked = [
            RankedPaper(
                paper=_paper(
                    f"Noise paper {index}",
                    abstract=f"Topic fragment {index} for macro clustering.",
                ),
                rank_score=0.9 - (index * 0.05),
            )
            for index in range(6)
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
            embedder=FixedEmbeddingProvider(
                [
                    np.array([0.1 * index, 0.9, 0.0], dtype=np.float32)
                    for index in range(len(ranked))
                ]
            ),
        )

        assert 1 <= len(clusters) <= 4
        assert all(cluster.theme.startswith("Theme:") for cluster in clusters)
        assert not any("Unclustered:" in cluster.theme for cluster in clusters)
