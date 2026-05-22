# -*- coding: utf-8 -*-
"""Follow-up intent parsing and session-side paper filtering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from ..retrieval.models import EnhancedResearchReport, PaperAnalysis, RankedPaper, RetrievedPaper


class FollowUpIntent(str, Enum):
    """Classification of interactive follow-up commands."""

    NEW_QUERY = "new_query"
    FILTER = "filter"
    FOCUS = "focus"
    COMPARE = "compare"
    EXPORT = "export"
    HELP = "help"


@dataclass
class FilterCriteria:
    """Structured filter parameters parsed from user text."""

    min_year: int | None = None
    max_year: int | None = None
    keywords: list[str] | None = None


@dataclass
class FollowUpCommand:
    """Parsed follow-up command with intent and parameters."""

    intent: FollowUpIntent
    raw_text: str
    filter_criteria: FilterCriteria | None = None
    focus_keywords: list[str] | None = None
    export_formats: list[str] | None = None
    compare_aspect: str | None = None


_AFTER_YEAR = re.compile(r"\b(?:papers?\s+)?after\s+(\d{4})\b", re.I)
_BEFORE_YEAR = re.compile(r"\b(?:papers?\s+)?before\s+(\d{4})\b", re.I)
_FROM_YEAR = re.compile(r"\b(?:papers?\s+)?from\s+(\d{4})\b", re.I)
_IN_YEAR = re.compile(r"\b(?:papers?\s+)?in\s+(\d{4})\b", re.I)
_SINCE_YEAR = re.compile(r"\b(?:papers?\s+)?since\s+(\d{4})\b", re.I)
_FOCUS = re.compile(r"^(?:focus(?:\s+on)?|emphasize)\s+(.+)$", re.I)
_COMPARE = re.compile(r"^compare\s+(methodolog(?:y|ies)|datasets?|benchmarks?|approaches?)$", re.I)
_EXPORT = re.compile(r"^export\s+(?:citations?\s+)?(?P<formats>[a-z,/\s]+)$", re.I)
_FILTER_PREFIX = re.compile(r"^filter:\s*(.+)$", re.I)
_HELP = re.compile(r"^(?:help|\?)$", re.I)

_EXPORT_FORMAT_MAP = {
    "bibtex": "bibtex",
    "apa": "apa",
    "mla": "mla",
    "chicago": "chicago",
}


def _parse_export_formats(text: str) -> list[str]:
    raw = text.replace("/", ",")
    parts = [part.strip().lower() for part in raw.split(",") if part.strip()]
    return [_EXPORT_FORMAT_MAP[part] for part in parts if part in _EXPORT_FORMAT_MAP]


def _extract_filter_criteria(text: str) -> FilterCriteria | None:
    criteria = FilterCriteria()
    matched = False

    for pattern in (_SINCE_YEAR, _AFTER_YEAR):
        match = pattern.search(text)
        if match:
            criteria.min_year = int(match.group(1))
            matched = True
            break

    match = _BEFORE_YEAR.search(text)
    if match:
        criteria.max_year = int(match.group(1))
        matched = True

    for pattern in (_FROM_YEAR, _IN_YEAR):
        match = pattern.search(text)
        if match:
            year = int(match.group(1))
            criteria.min_year = year
            criteria.max_year = year
            matched = True
            break

    return criteria if matched else None


def parse_follow_up(text: str) -> FollowUpCommand:
    """Parse user follow-up text into a structured command."""
    stripped = text.strip()
    lowered = stripped.lower()

    if _HELP.match(stripped):
        return FollowUpCommand(intent=FollowUpIntent.HELP, raw_text=stripped)

    export_match = _EXPORT.match(stripped)
    if export_match:
        formats = _parse_export_formats(export_match.group("formats"))
        if formats:
            return FollowUpCommand(
                intent=FollowUpIntent.EXPORT,
                raw_text=stripped,
                export_formats=formats,
            )

    compare_match = _COMPARE.match(stripped)
    if compare_match:
        return FollowUpCommand(
            intent=FollowUpIntent.COMPARE,
            raw_text=stripped,
            compare_aspect=compare_match.group(1).lower().rstrip("s"),
        )

    focus_match = _FOCUS.match(stripped)
    if focus_match:
        keywords = [word for word in re.findall(r"[a-z0-9]+", focus_match.group(1).lower()) if len(word) > 2]
        return FollowUpCommand(
            intent=FollowUpIntent.FOCUS,
            raw_text=stripped,
            focus_keywords=keywords or [focus_match.group(1).strip()],
        )

    filter_text = stripped
    prefix_match = _FILTER_PREFIX.match(stripped)
    if prefix_match:
        filter_text = prefix_match.group(1)

    criteria = _extract_filter_criteria(filter_text)
    if criteria:
        return FollowUpCommand(
            intent=FollowUpIntent.FILTER,
            raw_text=stripped,
            filter_criteria=criteria,
        )

    if any(
        phrase in lowered
        for phrase in ("papers after", "papers before", "papers from", "papers in", "papers since")
    ):
        criteria = _extract_filter_criteria(stripped)
        if criteria:
            return FollowUpCommand(
                intent=FollowUpIntent.FILTER,
                raw_text=stripped,
                filter_criteria=criteria,
            )

    return FollowUpCommand(intent=FollowUpIntent.NEW_QUERY, raw_text=stripped)


def _paper_matches_criteria(paper: RetrievedPaper, criteria: FilterCriteria) -> bool:
    if criteria.min_year is not None and (paper.year is None or paper.year < criteria.min_year):
        return False
    if criteria.max_year is not None and (paper.year is None or paper.year > criteria.max_year):
        return False
    if criteria.keywords:
        haystack = " ".join(
            [
                paper.title.lower(),
                (paper.abstract or "").lower(),
                " ".join(paper.keywords).lower(),
            ]
        )
        if not all(keyword.lower() in haystack for keyword in criteria.keywords):
            return False
    return True


def filter_ranked_papers(
    ranked_papers: list[RankedPaper],
    criteria: FilterCriteria,
) -> list[RankedPaper]:
    """Filter ranked papers by year and keyword criteria."""
    return [item for item in ranked_papers if _paper_matches_criteria(item.paper, criteria)]


def boost_ranked_papers(
    ranked_papers: list[RankedPaper],
    keywords: list[str],
    boost: float = 0.15,
) -> list[RankedPaper]:
    """Re-rank papers by boosting scores when focus keywords appear."""
    if not keywords:
        return ranked_papers

    boosted: list[RankedPaper] = []
    for item in ranked_papers:
        haystack = " ".join(
            [
                item.paper.title.lower(),
                (item.paper.abstract or "").lower(),
                " ".join(item.paper.keywords).lower(),
            ]
        )
        hits = sum(1 for keyword in keywords if keyword.lower() in haystack)
        score = item.rank_score + (boost * hits)
        boosted.append(
            RankedPaper(
                paper=item.paper,
                rank_score=min(score, 1.0),
                score_breakdown={
                    **item.score_breakdown,
                    "focus_boost": boost * hits,
                },
            )
        )

    return sorted(boosted, key=lambda paper: paper.rank_score, reverse=True)


def filter_report_analyses(
    report: EnhancedResearchReport,
    allowed_ids: set[str],
) -> EnhancedResearchReport:
    """Return a copy of the report limited to selected paper IDs."""
    filtered_papers = [
        paper
        for paper in report.papers
        if paper.paper_id in allowed_ids or paper.title in allowed_ids
    ]
    filtered_index = {
        paper_id: key
        for paper_id, key in report.citation_index.items()
        if paper_id in allowed_ids
    }
    filtered_clusters = [
        cluster.model_copy(
            update={
                "paper_ids": [pid for pid in cluster.paper_ids if pid in allowed_ids],
            }
        )
        for cluster in report.clusters
    ]
    filtered_clusters = [cluster for cluster in filtered_clusters if cluster.paper_ids]

    return report.model_copy(
        update={
            "papers": filtered_papers,
            "clusters": filtered_clusters,
            "citation_index": filtered_index,
            "executive_summary": (
                f"Filtered view showing {len(filtered_papers)} paper(s) "
                f"from the original query: {report.query}."
            ),
        }
    )


def analyses_from_ranked(ranked_papers: list[RankedPaper], base: list[PaperAnalysis]) -> list[PaperAnalysis]:
    """Map filtered ranked papers back to existing analyses where possible."""
    by_id = {analysis.paper_id: analysis for analysis in base if analysis.paper_id}
    by_title = {analysis.title: analysis for analysis in base}

    selected: list[PaperAnalysis] = []
    for item in ranked_papers:
        paper = item.paper
        analysis = by_id.get(paper.paper_id) or by_title.get(paper.title)
        if analysis:
            selected.append(analysis)
        else:
            selected.append(
                PaperAnalysis(
                    paper_id=paper.paper_id,
                    title=paper.title,
                    year=paper.year,
                    venue=paper.venue,
                    url=paper.url,
                    doi=paper.doi,
                )
            )
    return selected


def follow_up_help_text() -> str:
    """Return help text for interactive follow-up commands."""
    return (
        "Follow-up commands (no full re-retrieval):\n"
        "  • papers after 2023 / papers before 2020 / papers from 2022\n"
        "  • focus on transformer approaches\n"
        "  • compare methodologies\n"
        "  • export bibtex,apa,mla,chicago\n"
        "Enter a new research query for a full pipeline run."
    )
