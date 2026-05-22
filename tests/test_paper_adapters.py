# -*- coding: utf-8 -*-
"""Tests for pipeline paper adapter helpers."""

from src.core.paper_adapters import ensure_ranked_papers
from src.retrieval.models import RankedPaper, RetrievedPaper


def test_ensure_ranked_papers_from_retrieved() -> None:
    papers = [
        RetrievedPaper(title="Transformer Attention", abstract="Self-attention models", source="openalex"),
        RetrievedPaper(title="Attention Is All You Need", abstract="Transformers", source="openalex"),
    ]
    ranked, warnings = ensure_ranked_papers(papers, "transformer attention")

    assert warnings
    assert len(ranked) == 2
    assert all(isinstance(item, RankedPaper) for item in ranked)
    assert ranked[0].rank_score >= ranked[1].rank_score


def test_ensure_ranked_papers_passthrough() -> None:
    paper = RetrievedPaper(title="Test", abstract="abc", source="openalex")
    ranked_input = [RankedPaper(paper=paper, rank_score=0.9, score_breakdown={})]

    ranked, warnings = ensure_ranked_papers(ranked_input, "test")

    assert not warnings
    assert ranked == ranked_input
