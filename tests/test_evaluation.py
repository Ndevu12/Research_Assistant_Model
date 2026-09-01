# -*- coding: utf-8 -*-
"""Tests for the golden-set evaluation harness."""

from __future__ import annotations

import pytest

from src.config.settings import AppSettings
from src.evaluation.citation_validity import check_citation_validity
from src.evaluation.dataset import load_golden_dataset
from src.evaluation.harness import format_report, run_golden_evaluation
from src.evaluation.metrics import mrr, ndcg_at_k, recall_at_k
from src.retrieval.models import RetrievedPaper


class TestMetrics:
    def test_recall_at_k(self) -> None:
        ranked = ["a", "b", "c", "d"]
        assert recall_at_k(ranked, {"a", "c"}, 2) == pytest.approx(0.5)
        assert recall_at_k(ranked, {"a", "c"}, 4) == pytest.approx(1.0)
        assert recall_at_k(ranked, set(), 4) == 0.0

    def test_mrr(self) -> None:
        assert mrr(["x", "a", "b"], {"a", "b"}) == pytest.approx(0.5)
        assert mrr(["a"], {"a"}) == pytest.approx(1.0)
        assert mrr(["x", "y"], {"a"}) == 0.0

    def test_ndcg_perfect_ordering_is_one(self) -> None:
        relevance = {"a": 2, "b": 1, "c": 0}
        assert ndcg_at_k(["a", "b", "c"], relevance, 3) == pytest.approx(1.0)

    def test_ndcg_penalizes_inverted_ordering(self) -> None:
        relevance = {"a": 2, "b": 1, "c": 0}
        inverted = ndcg_at_k(["c", "b", "a"], relevance, 3)
        assert 0.0 < inverted < 1.0

    def test_ndcg_empty_relevance_is_zero(self) -> None:
        assert ndcg_at_k(["a"], {}, 5) == 0.0


class TestCitationValidity:
    def test_flags_malformed_doi_and_implausible_year(self) -> None:
        papers = [
            RetrievedPaper(title="Good", provider="t", doi="10.1234/abc", year=2020),
            RetrievedPaper(title="Bad DOI", provider="t", doi="not-a-doi", year=2020),
            RetrievedPaper(
                title="Future", provider="t", doi="10.1/x", year=2999
            ),
        ]

        result = check_citation_validity(papers, current_year=2026)

        assert result.checked == 3
        assert result.valid == 1
        flat = [issue for issues in result.issues.values() for issue in issues]
        assert "malformed_doi" in flat
        assert "implausible_year" in flat

    def test_paper_without_locator_is_flagged(self) -> None:
        result = check_citation_validity(
            [RetrievedPaper(title="No links", provider="t", year=2020)]
        )
        flat = [issue for issues in result.issues.values() for issue in issues]
        assert "no_locator" in flat


class TestGoldenDataset:
    def test_dataset_loads_and_is_well_formed(self) -> None:
        dataset = load_golden_dataset()

        assert len(dataset.queries) >= 5
        for query in dataset.queries:
            assert len(query.candidates) >= 6
            assert query.relevant_titles, f"query {query.query!r} has no relevant papers"
            irrelevant = [c for c in query.candidates if c.relevance == 0]
            assert irrelevant, f"query {query.query!r} has no negative candidates"


class TestGoldenEvaluation:
    """Regression floors for ranking quality on the golden set.

    Floors are set below the measured keyword-only baseline (mean R@5 0.93,
    nDCG@10 0.98, MRR 1.0) so they hold with or without the embedding
    backend; a change that drops below them has genuinely hurt ranking.
    """

    @pytest.fixture(scope="class")
    def report(self):
        return run_golden_evaluation(settings=AppSettings())

    def test_mean_recall_at_5_floor(self, report) -> None:
        mean_r5 = sum(q.recall_at_5 for q in report.queries) / len(report.queries)
        assert mean_r5 >= 0.80

    def test_mean_ndcg_floor(self, report) -> None:
        assert report.mean_ndcg_at_10 >= 0.85

    def test_mean_mrr_floor(self, report) -> None:
        assert report.mean_mrr >= 0.85

    def test_citation_validity_floor(self, report) -> None:
        assert report.citation_validity.validity_rate >= 0.90

    def test_report_renders(self, report) -> None:
        rendered = format_report(report)
        assert "Golden-set evaluation" in rendered
        assert "citation validity" in rendered
