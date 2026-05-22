# -*- coding: utf-8 -*-
"""Tests for interactive session follow-up filters."""

from __future__ import annotations

import pytest

from src.memory.filters import (
    FilterCriteria,
    FollowUpIntent,
    boost_ranked_papers,
    filter_ranked_papers,
    filter_report_analyses,
    parse_follow_up,
)
from src.retrieval.models import EnhancedResearchReport, PaperAnalysis, RankedPaper, RetrievedPaper


def _ranked(title: str, year: int, score: float = 0.5) -> RankedPaper:
    paper = RetrievedPaper(title=title, year=year, provider="openalex", doi=f"10.1/{title[:4]}")
    return RankedPaper(paper=paper, rank_score=score)


def _sample_report() -> EnhancedResearchReport:
    return EnhancedResearchReport(
        query="transformers",
        executive_summary="Original summary",
        papers=[
            PaperAnalysis(paper_id="10.1/Attn", title="Attention", year=2017),
            PaperAnalysis(paper_id="10.1/BERT", title="BERT", year=2019),
            PaperAnalysis(paper_id="10.1/GPT", title="GPT-3", year=2020),
        ],
        citation_index={
            "10.1/Attn": "a2017",
            "10.1/BERT": "b2019",
            "10.1/GPT": "g2020",
        },
    )


class TestFollowUpParsing:
    def test_filter_after_year(self) -> None:
        cmd = parse_follow_up("papers after 2019")
        assert cmd.intent == FollowUpIntent.FILTER
        assert cmd.filter_criteria is not None
        assert cmd.filter_criteria.min_year == 2019

    def test_filter_before_year(self) -> None:
        cmd = parse_follow_up("papers before 2019")
        assert cmd.intent == FollowUpIntent.FILTER
        assert cmd.filter_criteria is not None
        assert cmd.filter_criteria.max_year == 2019

    def test_focus_command(self) -> None:
        cmd = parse_follow_up("focus on transformer approaches")
        assert cmd.intent == FollowUpIntent.FOCUS
        assert "transformer" in (cmd.focus_keywords or [])

    def test_compare_command(self) -> None:
        cmd = parse_follow_up("compare methodologies")
        assert cmd.intent == FollowUpIntent.COMPARE

    def test_export_command(self) -> None:
        cmd = parse_follow_up("export bibtex,apa")
        assert cmd.intent == FollowUpIntent.EXPORT
        assert cmd.export_formats == ["bibtex", "apa"]

    def test_new_query_default(self) -> None:
        cmd = parse_follow_up("deep learning for NLP")
        assert cmd.intent == FollowUpIntent.NEW_QUERY


class TestPaperFiltering:
    def test_filter_ranked_papers_by_year(self) -> None:
        papers = [_ranked("A", 2017), _ranked("B", 2019), _ranked("C", 2021)]
        filtered = filter_ranked_papers(papers, FilterCriteria(min_year=2019))
        assert len(filtered) == 2
        assert all(item.paper.year >= 2019 for item in filtered)

    def test_boost_ranked_papers_by_keywords(self) -> None:
        papers = [
            RankedPaper(
                paper=RetrievedPaper(
                    title="Transformer Architecture",
                    provider="openalex",
                ),
                rank_score=0.45,
            ),
            RankedPaper(
                paper=RetrievedPaper(
                    title="Recurrent Networks",
                    provider="openalex",
                ),
                rank_score=0.6,
            ),
        ]
        boosted = boost_ranked_papers(papers, ["transformer"])
        assert boosted[0].paper.title == "Transformer Architecture"
        assert boosted[0].rank_score > 0.4

    def test_filter_report_analyses(self) -> None:
        report = _sample_report()
        filtered = filter_report_analyses(report, {"10.1/BERT", "10.1/GPT"})
        assert len(filtered.papers) == 2
        assert "10.1/Attn" not in filtered.citation_index
        assert "Filtered view" in filtered.executive_summary
