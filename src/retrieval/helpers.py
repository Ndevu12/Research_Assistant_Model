# -*- coding: utf-8 -*-
"""Helper functions for the retrieval module."""

import re
from typing import Optional

from .models import RetrievedPaper


def _normalize_title(t: str) -> str:
    """Normalize a paper title for comparison."""
    t = t.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", "", t)
    return t


def _dedupe(papers: list[RetrievedPaper]) -> list[RetrievedPaper]:
    """Remove duplicate papers based on DOI and normalized title."""
    seen: set[tuple[Optional[str], str]] = set()
    out: list[RetrievedPaper] = []
    for p in papers:
        key = (p.doi.lower().strip() if p.doi else None, _normalize_title(p.title))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


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
