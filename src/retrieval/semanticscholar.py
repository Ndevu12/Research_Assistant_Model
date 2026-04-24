# -*- coding: utf-8 -*-
"""Semantic Scholar API client for the retrieval module."""

import asyncio
import os
from typing import Optional

import aiohttp

from .models import RetrievedPaper
from ..utils.message_formatter import MessageFormatter


async def search_semantic_scholar(session: aiohttp.ClientSession, query: str, limit: int = 8) -> list[RetrievedPaper]:
    """Search Semantic Scholar for papers matching the query."""
    url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    params = {"query": query, "limit": str(limit), "fields": "title,abstract,year,venue,url,externalIds"}
    headers = {}
    s2_key = os.getenv("S2_API_KEY")
    if s2_key:
        headers["x-api-key"] = s2_key

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with session.get(url, params=params, headers=headers, timeout=60) as r:
                if r.status == 429:
                    retry_after = r.headers.get("Retry-After", "60")
                    print(MessageFormatter.api_rate_limit_message("Semantic Scholar", retry_after))
                    await asyncio.sleep(int(retry_after))
                    continue
                r.raise_for_status()
                data = await r.json()
                break
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            print(MessageFormatter.api_retry_message("Semantic Scholar", attempt + 1, str(e)))
            await asyncio.sleep(2 ** attempt)
    else:
        print(MessageFormatter.api_max_retries_message("Semantic Scholar"))
        return []

    results = []
    for item in data.get("data", []) or []:
        external = item.get("externalIds") or {}
        doi = external.get("DOI")
        results.append(RetrievedPaper(
            title=item.get("title") or "Untitled",
            abstract=item.get("abstract"),
            year=item.get("year"),
            venue=item.get("venue"),
            url=item.get("url"),
            doi=(f"https://doi.org/{doi}" if doi and not str(doi).startswith("http") else doi),
            source="semanticscholar",
        ))
    return results
