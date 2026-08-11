# -*- coding: utf-8 -*-
"""Semantic Scholar retrieval provider."""

from __future__ import annotations

import asyncio
import os

import aiohttp

from ..models import RetrievedPaper
from ...utils.logging_system import logger
from ...utils.message_formatter import MessageFormatter
from .base import RetrievalProvider


class SemanticScholarProvider(RetrievalProvider):
    """Retrieval provider backed by the Semantic Scholar bulk search API."""

    name = "semantic_scholar"
    _search_url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    _fields = "title,abstract,year,venue,url,externalIds"

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        api_key = os.getenv("S2_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key
        return headers

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        resolved_limit = self.resolve_limit(limit)
        params = {
            "query": query,
            "limit": str(resolved_limit),
            "fields": self._fields,
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with session.get(
                    self._search_url,
                    params=params,
                    headers=self._headers(),
                    timeout=60,
                ) as response:
                    if response.status == 429:
                        retry_after = response.headers.get("Retry-After", "60")
                        logger.warning(
                            MessageFormatter.api_rate_limit_message(
                                "Semantic Scholar",
                                retry_after,
                            )
                        )
                        await asyncio.sleep(int(retry_after))
                        continue
                    response.raise_for_status()
                    data = await response.json()
                    break
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == max_retries - 1:
                    raise
                logger.warning(
                    MessageFormatter.api_retry_message(
                        "Semantic Scholar",
                        attempt + 1,
                        str(exc),
                    )
                )
                await asyncio.sleep(2 ** attempt)
        else:
            logger.warning(MessageFormatter.api_max_retries_message("Semantic Scholar"))
            return []

        return [self.normalize(item) for item in data.get("data", []) or []][:resolved_limit]

    def normalize(self, raw: dict) -> RetrievedPaper:
        external = raw.get("externalIds") or {}
        doi = external.get("DOI")
        if doi and not str(doi).startswith("http"):
            doi = f"https://doi.org/{doi}"

        return RetrievedPaper(
            title=raw.get("title") or "Untitled",
            abstract=raw.get("abstract"),
            year=raw.get("year"),
            venue=raw.get("venue"),
            url=raw.get("url"),
            doi=doi,
            provider=self.name,
            raw_metadata=raw,
        )

    async def _ping(self, session: aiohttp.ClientSession) -> bool:
        async with session.get(
            self._search_url,
            params={"query": "test", "limit": "1", "fields": "title"},
            headers=self._headers(),
            timeout=15,
        ) as response:
            response.raise_for_status()
            return True
