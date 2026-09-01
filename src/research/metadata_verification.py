# -*- coding: utf-8 -*-
"""Cross-provider metadata reconciliation for duplicate paper clusters.

When the same paper is retrieved from several providers, the duplicate
cluster carries independent metadata observations. Instead of discarding
all but the best record, the cluster is reconciled into a single record:
missing fields are filled from other members, disagreements are resolved
by consensus, and every decision is recorded so downstream stages (and
report readers) can tell verified metadata from single-source metadata.

Conflict flags are appended to the shared ``metadata_sanity_flags`` list,
so the existing duplicate-preference and ranking penalties apply to
records with unresolved disagreements.
"""

from __future__ import annotations

from collections import Counter

from ..retrieval.models import RetrievedPaper
from .metadata_sanity import metadata_quality_key, normalize_doi

_METADATA_FLAGS_KEY = "metadata_sanity_flags"
VERIFICATION_KEY = "metadata_verification"


def _flags(paper: RetrievedPaper) -> list[str]:
    raw = paper.raw_metadata.get(_METADATA_FLAGS_KEY, [])
    return [str(item) for item in raw] if isinstance(raw, list) else []


def _consensus_year(members: list[RetrievedPaper]) -> tuple[int | None, bool]:
    """Return (majority year, conflict?) across members that report a year."""
    years = [paper.year for paper in members if paper.year is not None]
    if not years:
        return None, False
    counts = Counter(years)
    year, votes = counts.most_common(1)[0]
    conflict = len(counts) > 1
    has_majority = votes > len(years) / 2 or len(counts) == 1
    return (year if has_majority else None), conflict


def _distinct_dois(members: list[RetrievedPaper]) -> set[str]:
    return {normalize_doi(paper.doi) for paper in members if paper.doi}


def _longest_abstract(members: list[RetrievedPaper]) -> str | None:
    abstracts = [paper.abstract for paper in members if paper.abstract]
    return max(abstracts, key=len) if abstracts else None


def _first_value(members: list[RetrievedPaper], field: str) -> object | None:
    for paper in members:
        value = getattr(paper, field)
        if value:
            return value
    return None


def reconcile_duplicate_cluster(members: list[RetrievedPaper]) -> RetrievedPaper:
    """Merge a duplicate cluster into one cross-verified record.

    The highest-quality member (by :func:`metadata_quality_key`) is the base;
    the other members fill gaps and vote on disputed fields.
    """
    if len(members) == 1:
        return members[0]

    ordered = sorted(members, key=metadata_quality_key, reverse=True)
    base = ordered[0]
    updates: dict[str, object] = {}
    flags = _flags(base)
    conflicts: list[str] = []
    filled: list[str] = []

    majority_year, year_conflict = _consensus_year(ordered)
    if year_conflict:
        conflicts.append("year")
        flags.append("year_conflict")
    if majority_year is not None and base.year != majority_year:
        updates["year"] = majority_year
        filled.append("year")

    dois = _distinct_dois(ordered)
    if len(dois) > 1:
        conflicts.append("doi")
        flags.append("doi_conflict")
    elif not base.doi and dois:
        updates["doi"] = next(paper.doi for paper in ordered if paper.doi)
        filled.append("doi")

    for field in ("venue", "url"):
        if not getattr(base, field):
            value = _first_value(ordered, field)
            if value:
                updates[field] = value
                filled.append(field)

    if not base.abstract:
        abstract = _longest_abstract(ordered)
        if abstract:
            updates["abstract"] = abstract
            filled.append("abstract")

    citation_counts = [p.citation_count for p in ordered if p.citation_count is not None]
    if citation_counts:
        best_count = max(citation_counts)
        if base.citation_count != best_count:
            updates["citation_count"] = best_count
            filled.append("citation_count")

    providers = sorted({paper.provider for paper in ordered if paper.provider})
    verification = {
        "providers": providers,
        "cross_verified": len(providers) >= 2 and not conflicts,
        "conflicts": conflicts,
        "filled_fields": sorted(set(filled)),
    }

    raw_metadata = {
        **base.raw_metadata,
        _METADATA_FLAGS_KEY: sorted(set(flags)),
        VERIFICATION_KEY: verification,
    }
    return base.model_copy(update={**updates, "raw_metadata": raw_metadata})
