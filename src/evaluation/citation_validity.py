# -*- coding: utf-8 -*-
"""Offline citation-validity checks for retrieved papers.

These checks are deterministic and network-free so they can run in CI:
DOI format, plausible publication year, and minimum metadata presence.
Live DOI resolution belongs to a future live-evaluation mode.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from ..research.metadata_sanity import normalize_doi
from ..retrieval.models import RetrievedPaper

_DOI_PREFIX = "10."
_OLDEST_PLAUSIBLE_YEAR = 1800


class CitationValidityResult(BaseModel):
    """Aggregate citation-validity outcome for a set of papers."""

    checked: int = 0
    valid: int = 0
    issues: dict[str, list[str]] = Field(default_factory=dict)

    @property
    def validity_rate(self) -> float:
        if self.checked == 0:
            return 1.0
        return self.valid / self.checked


def _paper_issues(paper: RetrievedPaper, current_year: int) -> list[str]:
    issues: list[str] = []

    if not paper.title or not paper.title.strip():
        issues.append("missing_title")

    if paper.doi:
        normalized = normalize_doi(paper.doi)
        if not normalized.startswith(_DOI_PREFIX) or "/" not in normalized:
            issues.append("malformed_doi")

    if paper.year is not None and not (
        _OLDEST_PLAUSIBLE_YEAR <= paper.year <= current_year + 1
    ):
        issues.append("implausible_year")

    if not paper.doi and not paper.url:
        issues.append("no_locator")

    return issues


def check_citation_validity(
    papers: list[RetrievedPaper],
    *,
    current_year: int | None = None,
) -> CitationValidityResult:
    """Run offline validity checks over a batch of papers."""
    year_now = current_year if current_year is not None else date.today().year
    result = CitationValidityResult(checked=len(papers))

    for paper in papers:
        issues = _paper_issues(paper, year_now)
        if issues:
            result.issues[paper.paper_id] = issues
        else:
            result.valid += 1

    return result
