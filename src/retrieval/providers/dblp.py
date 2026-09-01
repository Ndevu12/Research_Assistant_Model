# -*- coding: utf-8 -*-
"""DBLP retrieval provider backed by the DBLP publication search API.

DBLP provides authoritative computer-science bibliography metadata (titles,
venues, years, DOIs) but no abstracts.
"""

from __future__ import annotations

import re

import aiohttp

from ..models import RetrievedPaper
from .base import RetrievalProvider


class DblpProvider(RetrievalProvider):
    """Retrieval provider for the DBLP computer-science bibliography."""

    name = "dblp"
    _search_url = "https://dblp.org/search/publ/api"

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        resolved_limit = self.resolve_limit(limit)
        data = await self._request_with_retry(
            session,
            self._search_url,
            params={"q": query, "format": "json", "h": str(resolved_limit)},
        )

        hits = (((data or {}).get("result") or {}).get("hits") or {}).get("hit") or []
        return [self.normalize(hit) for hit in hits][:resolved_limit]

    async def _ping(self, session: aiohttp.ClientSession) -> bool:
        data = await self._request_with_retry(
            session,
            self._search_url,
            params={"q": "algorithm", "format": "json", "h": "1"},
            timeout=15,
            max_retries=1,
        )
        return bool((data or {}).get("result"))

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
        if not authors and info.get("authors"):
            author_field = info["authors"].get("author")
            if isinstance(author_field, dict):
                authors = [author_field.get("text", "")]
            elif isinstance(author_field, list):
                authors = [
                    item.get("text", item) if isinstance(item, dict) else str(item)
                    for item in author_field
                ]
            elif author_field:
                authors = [str(author_field)]
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
