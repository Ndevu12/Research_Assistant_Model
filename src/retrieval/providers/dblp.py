# -*- coding: utf-8 -*-
"""DBLP retrieval provider (Phase 3 stub).

Future flow: DBLP JSON search API with venue-aware ranking and author
disambiguation for computer-science bibliography coverage.
"""

from __future__ import annotations

import re
from typing import ClassVar

from ..models import RetrievedPaper
from ._stub_base import StubRetrievalProvider


class DblpProvider(StubRetrievalProvider):
    """Retrieval provider stub for DBLP."""

    name = "dblp"
    _stub_message: ClassVar[str] = (
        "DBLP provider is not yet implemented. "
        "Future versions will query the DBLP JSON search API."
    )

    def normalize(self, raw: dict) -> RetrievedPaper:
        """Convert a DBLP JSON record into a RetrievedPaper."""
        info = raw.get("info") or raw
        title = info.get("title") or raw.get("title") or "Untitled"
        title = re.sub(r"\.$", "", str(title))

        year = info.get("year") or raw.get("year")
        if year is not None:
            year = int(year)

        venue = info.get("venue") or raw.get("venue")
        if isinstance(venue, list):
            venue = venue[0] if venue else None

        authors = raw.get("authors") or []
        if not authors and raw.get("author"):
            author_field = raw["author"]
            if isinstance(author_field, dict):
                authors = [author_field.get("text", "")]
            elif isinstance(author_field, list):
                authors = [
                    item.get("text", item) if isinstance(item, dict) else str(item)
                    for item in author_field
                ]
            else:
                authors = [str(author_field)]

        url = raw.get("url") or info.get("ee") or info.get("url")
        if isinstance(url, list):
            url = url[0] if url else None

        doi = info.get("doi") or raw.get("doi")
        if doi and not str(doi).startswith("http"):
            doi = f"https://doi.org/{doi}"

        return RetrievedPaper(
            title=title,
            abstract=info.get("abstract") or raw.get("abstract"),
            year=year,
            venue=venue,
            url=url,
            doi=doi or None,
            provider=self.name,
            authors=[name for name in authors if name],
            raw_metadata=raw,
        )
