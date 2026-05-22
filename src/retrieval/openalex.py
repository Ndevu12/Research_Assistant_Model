# -*- coding: utf-8 -*-
"""OpenAlex API client for the retrieval module (deprecated shim)."""

from __future__ import annotations

import warnings

import aiohttp

from .models import RetrievedPaper
from .providers.openalex import OpenAlexProvider

_provider = OpenAlexProvider()


async def search_openalex(
    session: aiohttp.ClientSession,
    query: str,
    per_page: int = 8,
) -> list[RetrievedPaper]:
    """Search OpenAlex for papers matching the query."""
    warnings.warn(
        "search_openalex is deprecated; use OpenAlexProvider from "
        "src.retrieval.providers instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _provider.search(session, query, limit=per_page)
