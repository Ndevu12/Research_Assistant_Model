# -*- coding: utf-8 -*-
"""Canonical metadata checks and corrections for retrieved papers."""

from __future__ import annotations

import re
from datetime import date

from ..retrieval.models import RetrievedPaper
from .canonical_works import CanonicalWork, match_canonical_work

DEFAULT_YEAR_TOLERANCE = 1
_METADATA_FLAGS_KEY = "metadata_sanity_flags"
_DOI_FORMAT = re.compile(r"^10\.\d{4,9}/\S+$")


def _current_year() -> int:
    return date.today().year


def normalize_doi(doi: str) -> str:
    """Strip common DOI URL prefixes for prefix matching."""
    normalized = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized.strip()


def _valid_doi_format(doi: str) -> bool:
    """Return True when a DOI string matches the generic ``10.xxxx/suffix`` pattern."""
    return bool(_DOI_FORMAT.match(normalize_doi(doi)))


def _flag_list(paper: RetrievedPaper) -> list[str]:
    raw = paper.raw_metadata.get(_METADATA_FLAGS_KEY, [])
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def _with_flags(paper: RetrievedPaper, flags: list[str], **updates: object) -> RetrievedPaper:
    unique_flags = sorted(set(flags))
    raw_metadata = {
        **paper.raw_metadata,
        _METADATA_FLAGS_KEY: unique_flags,
    }
    return paper.model_copy(update={**updates, "raw_metadata": raw_metadata})


def check_suspicious_year(
    paper: RetrievedPaper,
    canonical: CanonicalWork | None = None,
    *,
    current_year: int | None = None,
    year_tolerance: int = DEFAULT_YEAR_TOLERANCE,
) -> bool:
    """Return True when the publication year looks unreliable."""
    if paper.year is None:
        return False

    year_now = current_year if current_year is not None else _current_year()
    if paper.year > year_now + 1:
        return True

    if canonical and canonical.year is not None:
        return abs(paper.year - canonical.year) > year_tolerance

    return False


def check_doi_prefix_mismatch(paper: RetrievedPaper, canonical: CanonicalWork) -> bool:
    """Return True when a canonical paper's DOI does not match the expected prefix."""
    if not canonical.doi_prefix or not paper.doi:
        return False
    return not normalize_doi(paper.doi).startswith(canonical.doi_prefix.lower())


def sanitize_paper_metadata(
    paper: RetrievedPaper,
    works: list[CanonicalWork] | None = None,
    *,
    current_year: int | None = None,
    year_tolerance: int = DEFAULT_YEAR_TOLERANCE,
) -> RetrievedPaper:
    """Apply generic metadata checks and optional canonical corrections."""
    flags = _flag_list(paper)
    updates: dict[str, object] = {}

    year_now = current_year if current_year is not None else _current_year()
    if paper.year is not None and paper.year > year_now + 1:
        flags.append("future_year")

    if paper.doi and not _valid_doi_format(paper.doi):
        flags.append("invalid_doi_format")

    if works:
        canonical = match_canonical_work(paper.title, works)
        if canonical is not None:
            if check_suspicious_year(
                paper,
                canonical,
                current_year=year_now,
                year_tolerance=year_tolerance,
            ):
                flags.append("suspicious_year")
                if canonical.year is not None:
                    updates["year"] = canonical.year

            if check_doi_prefix_mismatch(paper, canonical):
                flags.append("doi_prefix_mismatch")

    if flags or updates:
        return _with_flags(paper, flags, **updates)
    return paper


def sanitize_papers_metadata(
    papers: list[RetrievedPaper],
    works: list[CanonicalWork] | None = None,
    *,
    current_year: int | None = None,
    year_tolerance: int = DEFAULT_YEAR_TOLERANCE,
) -> list[RetrievedPaper]:
    """Sanitize metadata for a batch of papers."""
    return [
        sanitize_paper_metadata(
            paper,
            works,
            current_year=current_year,
            year_tolerance=year_tolerance,
        )
        for paper in papers
    ]


def metadata_quality_key(paper: RetrievedPaper) -> tuple[int, int, int, int]:
    """Rank duplicate candidates; higher values are preferred."""
    flags = _flag_list(paper)
    abstract_len = len(paper.abstract or "")
    citation_count = paper.citation_count or 0
    metadata_score = int(bool(paper.doi)) + int(bool(paper.url))
    penalty = len(flags)
    return (citation_count, abstract_len, metadata_score, -penalty)
