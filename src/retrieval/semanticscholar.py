# -*- coding: utf-8 -*-
"""Semantic Scholar API client for the retrieval module (deprecated shim)."""

from __future__ import annotations

import warnings

import aiohttp

from .models import RetrievedPaper
from .providers.semantic_scholar import SemanticScholarProvider

_provider = SemanticScholarProvider()


async def search_semantic_scholar(
    session: aiohttp.ClientSession,
    query: str,
    limit: int = 8,
) -> list[RetrievedPaper]:
    """Search Semantic Scholar for papers matching the query."""
    warnings.warn(
        "search_semantic_scholar is deprecated; use SemanticScholarProvider from "
        "src.retrieval.providers instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _provider.search(session, query, limit=limit)
