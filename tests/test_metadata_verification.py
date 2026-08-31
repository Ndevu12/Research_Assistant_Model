# -*- coding: utf-8 -*-
"""Tests for cross-provider metadata reconciliation."""

from __future__ import annotations

from src.research.metadata_verification import (
    VERIFICATION_KEY,
    reconcile_duplicate_cluster,
)
from src.retrieval.deduplication import dedupe_by_metadata
from src.retrieval.models import RetrievedPaper


def _paper(provider: str, **overrides) -> RetrievedPaper:
    defaults = {
        "title": "Attention Is All You Need",
        "provider": provider,
    }
    defaults.update(overrides)
    return RetrievedPaper(**defaults)


def test_single_member_cluster_is_returned_unchanged() -> None:
    paper = _paper("openalex", year=2017)
    assert reconcile_duplicate_cluster([paper]) is paper


def test_majority_year_wins_and_conflict_is_flagged() -> None:
    merged = reconcile_duplicate_cluster(
        [
            _paper("semantic_scholar", year=2025, citation_count=90000, abstract="A" * 500),
            _paper("openalex", year=2017, citation_count=80000),
            _paper("crossref", year=2017),
        ]
    )

    assert merged.year == 2017
    verification = merged.raw_metadata[VERIFICATION_KEY]
    assert "year" in verification["conflicts"]
    assert "year_conflict" in merged.raw_metadata["metadata_sanity_flags"]


def test_missing_fields_are_filled_from_other_providers() -> None:
    merged = reconcile_duplicate_cluster(
        [
            _paper("openalex", year=2017, citation_count=90000),
            _paper(
                "crossref",
                year=2017,
                doi="10.48550/arXiv.1706.03762",
                venue="NeurIPS",
                url="https://example.org/attention",
                abstract="The dominant sequence transduction models are based on RNNs.",
            ),
        ]
    )

    assert merged.doi == "10.48550/arXiv.1706.03762"
    assert merged.venue == "NeurIPS"
    assert merged.url == "https://example.org/attention"
    assert merged.abstract is not None
    verification = merged.raw_metadata[VERIFICATION_KEY]
    assert set(verification["filled_fields"]) >= {"doi", "venue", "url", "abstract"}


def test_two_agreeing_providers_mark_cross_verified() -> None:
    merged = reconcile_duplicate_cluster(
        [
            _paper("openalex", year=2017, doi="10.1/abc"),
            _paper("semantic_scholar", year=2017, doi="https://doi.org/10.1/abc"),
        ]
    )

    verification = merged.raw_metadata[VERIFICATION_KEY]
    assert verification["cross_verified"] is True
    assert verification["providers"] == ["openalex", "semantic_scholar"]
    assert verification["conflicts"] == []


def test_disagreeing_dois_flag_conflict_and_block_cross_verification() -> None:
    merged = reconcile_duplicate_cluster(
        [
            _paper("openalex", year=2017, doi="10.1/abc"),
            _paper("semantic_scholar", year=2017, doi="10.9/zzz"),
        ]
    )

    verification = merged.raw_metadata[VERIFICATION_KEY]
    assert verification["cross_verified"] is False
    assert "doi" in verification["conflicts"]
    assert "doi_conflict" in merged.raw_metadata["metadata_sanity_flags"]


def test_citation_count_takes_the_maximum_observation() -> None:
    merged = reconcile_duplicate_cluster(
        [
            _paper("openalex", year=2017, citation_count=100, abstract="B" * 400),
            _paper("semantic_scholar", year=2017, citation_count=120000),
        ]
    )

    assert merged.citation_count == 120000


def test_metadata_dedup_reconciles_cross_provider_duplicates() -> None:
    papers = [
        _paper("openalex", year=2017, citation_count=90000),
        _paper("semantic_scholar", year=2017, doi="10.1/abc", venue="NeurIPS"),
        RetrievedPaper(title="A Different Paper", provider="openalex", year=2020),
    ]

    deduped = dedupe_by_metadata(papers)

    assert len(deduped) == 2
    merged = next(p for p in deduped if p.title == "Attention Is All You Need")
    assert merged.doi == "10.1/abc"
    assert merged.venue == "NeurIPS"
    assert merged.raw_metadata[VERIFICATION_KEY]["cross_verified"] is True
