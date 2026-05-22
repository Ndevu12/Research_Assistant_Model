# -*- coding: utf-8 -*-
"""Helper functions for the retrieval module."""

import re
from typing import Optional

from .models import RetrievedPaper


def _normalize_title(t: str) -> str:
    """Normalize a paper title for comparison."""
    from .deduplication import normalize_title

    return normalize_title(t)


def _dedupe(papers: list[RetrievedPaper]) -> list[RetrievedPaper]:
    """Remove duplicate papers based on DOI and normalized title."""
    from .deduplication import dedupe_by_metadata

    return dedupe_by_metadata(papers)


def _openalex_abstract_from_inverted_index(inv: Optional[dict[str, list[int]]]) -> Optional[str]:
    """Reconstruct abstract from OpenAlex's inverted index format."""
    if not inv:
        return None
    positions: dict[int, str] = {}
    for word, pos_list in inv.items():
        for pos in pos_list:
            positions[pos] = word
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions.keys()))
