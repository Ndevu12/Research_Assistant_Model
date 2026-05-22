# -*- coding: utf-8 -*-
"""OpenAlex retrieval provider."""

from __future__ import annotations

import asyncio

import aiohttp

from ..helpers import _openalex_abstract_from_inverted_index
from ..models import RetrievedPaper
from ...utils.message_formatter import MessageFormatter
from .base import RetrievalProvider


class OpenAlexProvider(RetrievalProvider):
    """Retrieval provider backed by the OpenAlex works API."""

    name = "openalex"
    _search_url = "https://api.openalex.org/works"
    _health_url = "https://api.openalex.org/works"

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        per_page = self.resolve_limit(limit)
        params = {"search": query, "per-page": str(per_page)}

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with session.get(
                    self._search_url,
                    params=params,
                    timeout=60,
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    break
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == max_retries - 1:
                    raise
                print(MessageFormatter.api_retry_message("OpenAlex", attempt + 1, str(exc)))
                await asyncio.sleep(2 ** attempt)

        return [self.normalize(item) for item in data.get("results", [])][:per_page]

    def normalize(self, raw: dict) -> RetrievedPaper:
        primary_location = raw.get("primary_location") or {}
        source = primary_location.get("source") or {}
        venue = source.get("display_name") or raw.get("host_venue", {}).get("display_name")
        url_out = raw.get("id") or primary_location.get("landing_page_url")

        return RetrievedPaper(
            title=raw.get("display_name") or "Untitled",
            abstract=_openalex_abstract_from_inverted_index(raw.get("abstract_inverted_index")),
            year=raw.get("publication_year"),
            venue=venue,
            url=url_out,
            doi=raw.get("doi"),
            provider=self.name,
            citation_count=raw.get("cited_by_count"),
            raw_metadata=raw,
        )

    async def _ping(self, session: aiohttp.ClientSession) -> bool:
        async with session.get(
            self._health_url,
            params={"per-page": "1"},
            timeout=15,
        ) as response:
            response.raise_for_status()
            return True
