# -*- coding: utf-8 -*-
"""OpenAlex API client for the retrieval module."""

import asyncio
from typing import Optional

import aiohttp

from .helpers import _openalex_abstract_from_inverted_index
from .models import RetrievedPaper


async def search_openalex(session: aiohttp.ClientSession, query: str, per_page: int = 8) -> list[RetrievedPaper]:
    """Search OpenAlex for papers matching the query."""
    url = "https://api.openalex.org/works"
    params = {"search": query, "per-page": str(per_page)}

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with session.get(url, params=params, timeout=60) as r:
                r.raise_for_status()
                data = await r.json()
                break
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            print(f"OpenAlex attempt {attempt + 1} failed: {e}. Retrying...")
            await asyncio.sleep(2 ** attempt)

    results = []
    for item in data.get("results", []):
        title = item.get("display_name") or "Untitled"
        year = item.get("publication_year")
        doi = item.get("doi")
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        venue = source.get("display_name") or item.get("host_venue", {}).get("display_name")
        abstract = _openalex_abstract_from_inverted_index(item.get("abstract_inverted_index"))
        url_out = item.get("id") or item.get("primary_location", {}).get("landing_page_url")
        results.append(RetrievedPaper(title=title, abstract=abstract, year=year,
                                      venue=venue, url=url_out, doi=doi, source="openalex"))
    return results
