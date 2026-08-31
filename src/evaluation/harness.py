# -*- coding: utf-8 -*-
"""Offline evaluation harness: runs ranking over golden candidates.

The harness feeds each golden query's labeled candidates through the real
deduplication and ranking stages (no network, no LLM) and scores the
resulting order against the relevance labels. Embeddings are used when the
backend is installed and fall back to keyword ranking otherwise, so the
harness runs in any environment, including CI.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ..config.settings import AppSettings
from ..evaluation.citation_validity import CitationValidityResult, check_citation_validity
from ..evaluation.dataset import GoldenDataset, GoldenQuery, load_golden_dataset
from ..evaluation.metrics import mrr, ndcg_at_k, recall_at_k
from ..research.ranking import rank_papers
from ..retrieval.deduplication import dedupe_by_metadata


class QueryEvaluation(BaseModel):
    """Metrics for a single golden query."""

    query: str
    domain: str
    recall_at_5: float
    recall_at_10: float
    ndcg_at_10: float
    mrr: float
    candidates: int
    relevant: int


class EvaluationReport(BaseModel):
    """Aggregate evaluation results across the golden set."""

    queries: list[QueryEvaluation] = Field(default_factory=list)
    citation_validity: CitationValidityResult = Field(
        default_factory=CitationValidityResult
    )
    embeddings_used: bool = False

    def _mean(self, values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @property
    def mean_recall_at_10(self) -> float:
        return self._mean([q.recall_at_10 for q in self.queries])

    @property
    def mean_ndcg_at_10(self) -> float:
        return self._mean([q.ndcg_at_10 for q in self.queries])

    @property
    def mean_mrr(self) -> float:
        return self._mean([q.mrr for q in self.queries])


def _try_embedder(settings: AppSettings):
    from ..embeddings import try_create_embedding_provider

    provider = try_create_embedding_provider(settings.embedding)
    if provider is None:
        return None
    try:
        provider.embed_texts(["embedding backend probe"])
    except Exception:
        return None
    return provider


def evaluate_query(
    golden: GoldenQuery,
    settings: AppSettings,
    embedder=None,
) -> QueryEvaluation:
    """Rank one golden query's candidates and score the ordering."""
    papers = dedupe_by_metadata([c.to_paper() for c in golden.candidates])
    config = settings.ranking.model_copy(update={"top_k": len(papers)})

    result = rank_papers(papers, golden.query, config=config, embedder=embedder)
    ranked_titles = [item.paper.title for item in result.ranked]

    relevant = golden.relevant_titles
    relevance = golden.relevance_by_title

    return QueryEvaluation(
        query=golden.query,
        domain=golden.domain,
        recall_at_5=recall_at_k(ranked_titles, relevant, 5),
        recall_at_10=recall_at_k(ranked_titles, relevant, 10),
        ndcg_at_10=ndcg_at_k(ranked_titles, relevance, 10),
        mrr=mrr(ranked_titles, relevant),
        candidates=len(golden.candidates),
        relevant=len(relevant),
    )


def run_golden_evaluation(
    settings: AppSettings | None = None,
    dataset: GoldenDataset | None = None,
    dataset_path: Path | None = None,
) -> EvaluationReport:
    """Evaluate ranking quality over the golden dataset."""
    resolved_settings = settings or AppSettings()
    resolved_dataset = dataset or load_golden_dataset(dataset_path)
    embedder = _try_embedder(resolved_settings)

    report = EvaluationReport(embeddings_used=embedder is not None)
    all_papers = []

    for golden in resolved_dataset.queries:
        report.queries.append(evaluate_query(golden, resolved_settings, embedder))
        all_papers.extend(c.to_paper() for c in golden.candidates)

    report.citation_validity = check_citation_validity(all_papers)
    return report


def format_report(report: EvaluationReport) -> str:
    """Render an evaluation report as a plain-text table."""
    lines = [
        "Golden-set evaluation "
        f"({'embedding' if report.embeddings_used else 'keyword'} ranking)",
        "",
        f"{'query':<44} {'R@5':>5} {'R@10':>5} {'nDCG@10':>8} {'MRR':>5}",
    ]
    for item in report.queries:
        label = item.query if len(item.query) <= 42 else item.query[:39] + "..."
        lines.append(
            f"{label:<44} {item.recall_at_5:>5.2f} {item.recall_at_10:>5.2f} "
            f"{item.ndcg_at_10:>8.2f} {item.mrr:>5.2f}"
        )
    lines.append("")
    lines.append(
        f"{'mean':<44} {'':>5} {report.mean_recall_at_10:>5.2f} "
        f"{report.mean_ndcg_at_10:>8.2f} {report.mean_mrr:>5.2f}"
    )
    validity = report.citation_validity
    lines.append(
        f"citation validity: {validity.valid}/{validity.checked} "
        f"({validity.validity_rate:.0%})"
    )
    return "\n".join(lines)
