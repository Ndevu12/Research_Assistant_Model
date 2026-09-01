# -*- coding: utf-8 -*-
"""Resolve open-access PDF URLs from retrieved-paper metadata.

Resolution is metadata-first and free of extra network calls: arXiv IDs
map directly to PDF URLs, OpenAlex work records already carry open-access
locations in their raw metadata, and CORE results expose direct download
URLs. Papers without any of these simply resolve to ``None`` — full-text
grounding is best-effort by design.
"""

from __future__ import annotations

import re

from ..retrieval.models import RetrievedPaper

_ARXIV_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})(v\d+)?", re.IGNORECASE)
_ARXIV_DOI_RE = re.compile(r"10\.48550/arxiv\.([0-9]{4}\.[0-9]{4,5})", re.IGNORECASE)


def _arxiv_pdf_url(paper: RetrievedPaper) -> str | None:
    for candidate in (paper.url or "", paper.doi or ""):
        match = _ARXIV_ID_RE.search(candidate) or _ARXIV_DOI_RE.search(candidate)
        if match:
            return f"https://arxiv.org/pdf/{match.group(1)}"
    return None


def _openalex_pdf_url(paper: RetrievedPaper) -> str | None:
    raw = paper.raw_metadata
    open_access = raw.get("open_access") or {}
    best_location = raw.get("best_oa_location") or {}
    primary = raw.get("primary_location") or {}

    for candidate in (
        best_location.get("pdf_url"),
        primary.get("pdf_url"),
        open_access.get("oa_url"),
        best_location.get("landing_page_url") if best_location.get("is_oa") else None,
    ):
        if candidate:
            return str(candidate)
    return None


def _core_pdf_url(paper: RetrievedPaper) -> str | None:
    raw = paper.raw_metadata
    candidate = raw.get("downloadUrl") or (raw.get("sourceFulltextUrls") or [None])[0]
    return str(candidate) if candidate else None


def resolve_pdf_url(paper: RetrievedPaper) -> str | None:
    """Return the most direct open-access PDF URL for a paper, if any."""
    for resolver in (_arxiv_pdf_url, _openalex_pdf_url, _core_pdf_url):
        url = resolver(paper)
        if url:
            return url
    return None
