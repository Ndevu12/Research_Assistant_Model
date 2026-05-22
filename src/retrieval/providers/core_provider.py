# -*- coding: utf-8 -*-
"""CORE retrieval provider (Phase 3 stub).

Future flow: CORE API v3 search with full-text availability flags, repository
metadata, and optional full-text download handoff to ``src.fulltext``.
"""

from __future__ import annotations

import re
from typing import ClassVar

from ..models import RetrievedPaper
from ._stub_base import StubRetrievalProvider


class CoreProvider(StubRetrievalProvider):
    """Retrieval provider stub for the CORE open-access aggregator."""

    name = "core"
    _stub_message: ClassVar[str] = (
        "CORE provider is not yet implemented. "
        "Future versions will query the CORE API v3 search endpoint."
    )

    def normalize(self, raw: dict) -> RetrievedPaper:
        """Convert a CORE API v3 record into a RetrievedPaper."""
        title = raw.get("title") or raw.get("displayName") or "Untitled"
        abstract = raw.get("abstract") or raw.get("description") or None

        year = raw.get("year") or raw.get("publishedDate")
        if isinstance(year, str):
            match = re.search(r"(\d{4})", year)
            year = int(match.group(1)) if match else None
        elif year is not None:
            year = int(year)

        doi = raw.get("doi")
        if doi and not str(doi).startswith("http"):
            doi = f"https://doi.org/{doi}"

        authors = raw.get("authors") or []
        if not authors and raw.get("author"):
            authors = [raw["author"]] if isinstance(raw["author"], str) else list(raw["author"])

        url = raw.get("downloadUrl") or raw.get("sourceFulltextUrls", [None])[0]
        if not url:
            url = raw.get("id") or raw.get("url")

        return RetrievedPaper(
            title=str(title),
            abstract=abstract,
            year=year,
            venue=raw.get("publisher") or raw.get("journals", [None])[0],
            url=url,
            doi=doi or None,
            provider=self.name,
            authors=[str(name) for name in authors if name],
            citation_count=raw.get("citationCount") or raw.get("citedByCount"),
            raw_metadata=raw,
        )
