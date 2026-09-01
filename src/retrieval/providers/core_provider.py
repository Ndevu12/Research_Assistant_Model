# -*- coding: utf-8 -*-
"""CORE retrieval provider backed by the CORE API v3.

CORE aggregates open-access research outputs and exposes full-text
availability flags, making it a natural feeder for the planned full-text
pipeline. The API requires a key (``CORE_API_KEY``); without one the
provider reports itself unhealthy and search fails with a clear message.
"""

from __future__ import annotations

import os
import re

import aiohttp

from ..models import RetrievedPaper
from .base import ProviderHealth, RetrievalProvider

_MISSING_KEY_MESSAGE = (
    "CORE provider requires the CORE_API_KEY environment variable "
    "(free keys at https://core.ac.uk/services/api)."
)


class CoreProvider(RetrievalProvider):
    """Retrieval provider for the CORE open-access aggregator."""

    name = "core"
    _search_url = "https://api.core.ac.uk/v3/search/works"

    @staticmethod
    def _api_key() -> str | None:
        return os.getenv("CORE_API_KEY") or None

    def _headers(self) -> dict[str, str]:
        api_key = self._api_key()
        if not api_key:
            raise RuntimeError(_MISSING_KEY_MESSAGE)
        return {"Authorization": f"Bearer {api_key}"}

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
            params={"q": query, "limit": str(resolved_limit)},
            headers=self._headers(),
        )
        results = (data or {}).get("results") or []
        return [self.normalize(item) for item in results][:resolved_limit]

    async def health_check(self, session: aiohttp.ClientSession) -> ProviderHealth:
        if not self._api_key():
            return ProviderHealth(
                provider=self.name,
                healthy=False,
                latency_ms=0.0,
                message=_MISSING_KEY_MESSAGE,
            )
        return await super().health_check(session)

    async def _ping(self, session: aiohttp.ClientSession) -> bool:
        data = await self._request_with_retry(
            session,
            self._search_url,
            params={"q": "science", "limit": "1"},
            headers=self._headers(),
            timeout=15,
            max_retries=1,
        )
        return "results" in (data or {})

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
        if authors and isinstance(authors[0], dict):
            authors = [author.get("name", "") for author in authors]
        if not authors and raw.get("author"):
            authors = [raw["author"]] if isinstance(raw["author"], str) else list(raw["author"])

        url = raw.get("downloadUrl") or (raw.get("sourceFulltextUrls") or [None])[0]
        if not url:
            url = raw.get("id") or raw.get("url")
            if isinstance(url, int):
                url = f"https://core.ac.uk/works/{url}"

        venue = raw.get("publisher")
        journals = raw.get("journals") or []
        if not venue and journals:
            first = journals[0]
            venue = first.get("title") if isinstance(first, dict) else first

        return RetrievedPaper(
            title=str(title),
            abstract=abstract,
            year=year,
            venue=venue,
            url=str(url) if url else None,
            doi=doi or None,
            provider=self.name,
            authors=[str(name) for name in authors if name],
            citation_count=raw.get("citationCount") or raw.get("citedByCount"),
            raw_metadata=raw,
        )
