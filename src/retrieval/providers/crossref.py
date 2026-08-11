# -*- coding: utf-8 -*-
"""CrossRef retrieval provider."""

from __future__ import annotations

import asyncio
import os
import re

import aiohttp

from ..models import RetrievedPaper
from ...utils.logging_system import logger
from ...utils.message_formatter import MessageFormatter
from .base import RetrievalProvider


class CrossRefProvider(RetrievalProvider):
    """Retrieval provider backed by the CrossRef REST API."""

    name = "crossref"
    _search_url = "https://api.crossref.org/works"

    def _headers(self) -> dict[str, str]:
        mailto = os.getenv("RA_CROSSREF_MAILTO") or os.getenv("CROSSREF_MAILTO")
        if mailto:
            return {"User-Agent": f"ResearchAssistant/1.0 (mailto:{mailto})"}
        return {"User-Agent": "ResearchAssistant/1.0"}

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        rows = self.resolve_limit(limit)
        params = {"query": query, "rows": str(rows)}

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
                                "CrossRef",
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
                logger.warning(MessageFormatter.api_retry_message("CrossRef", attempt + 1, str(exc)))
                await asyncio.sleep(2 ** attempt)
        else:
            logger.warning(MessageFormatter.api_max_retries_message("CrossRef"))
            return []

        message = data.get("message") or {}
        items = message.get("items") or []
        return [self.normalize(item) for item in items]

    @staticmethod
    def _extract_year(raw: dict) -> int | None:
        for key in ("published-print", "published-online", "created", "issued"):
            block = raw.get(key) or {}
            parts = block.get("date-parts") or []
            if parts and parts[0]:
                year = parts[0][0]
                if isinstance(year, int):
                    return year
        return None

    @staticmethod
    def _extract_authors(raw: dict) -> list[str]:
        authors: list[str] = []
        for author in raw.get("author") or []:
            given = author.get("given") or ""
            family = author.get("family") or ""
            name = " ".join(part for part in (given, family) if part).strip()
            if name:
                authors.append(name)
        return authors

    @staticmethod
    def _extract_title(raw: dict) -> str:
        titles = raw.get("title") or []
        if titles:
            return str(titles[0]).strip()
        return "Untitled"

    @staticmethod
    def _extract_venue(raw: dict) -> str | None:
        containers = raw.get("container-title") or []
        if containers:
            return str(containers[0]).strip()
        return None

    @staticmethod
    def _clean_abstract(raw: dict) -> str | None:
        abstract = raw.get("abstract")
        if not abstract:
            return None
        text = re.sub(r"<[^>]+>", " ", str(abstract))
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    def normalize(self, raw: dict) -> RetrievedPaper:
        doi = raw.get("DOI")
        if doi and not str(doi).startswith("http"):
            doi = f"https://doi.org/{doi}"

        return RetrievedPaper(
            title=self._extract_title(raw),
            abstract=self._clean_abstract(raw),
            year=self._extract_year(raw),
            venue=self._extract_venue(raw),
            url=raw.get("URL"),
            doi=doi,
            provider=self.name,
            citation_count=raw.get("is-referenced-by-count"),
            authors=self._extract_authors(raw),
            raw_metadata=raw,
        )

    async def _ping(self, session: aiohttp.ClientSession) -> bool:
        async with session.get(
            self._search_url,
            params={"rows": "1"},
            headers=self._headers(),
            timeout=15,
        ) as response:
            response.raise_for_status()
            return True
