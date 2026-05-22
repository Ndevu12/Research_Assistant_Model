# -*- coding: utf-8 -*-
"""Retrieval provider registry."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import aiohttp

from .arxiv import ArxivProvider
from .base import ProviderHealth, RetrievalProvider
from .core_provider import CoreProvider
from .crossref import CrossRefProvider
from .dblp import DblpProvider
from .openalex import OpenAlexProvider
from .pubmed import PubMedProvider
from .semantic_scholar import SemanticScholarProvider

if TYPE_CHECKING:
    from ...config.settings import AppSettings, ProviderConfig
    from ..models import RetrievedPaper

_PROVIDER_CLASSES: dict[str, type[RetrievalProvider]] = {
    OpenAlexProvider.name: OpenAlexProvider,
    SemanticScholarProvider.name: SemanticScholarProvider,
    ArxivProvider.name: ArxivProvider,
    CrossRefProvider.name: CrossRefProvider,
    PubMedProvider.name: PubMedProvider,
    CoreProvider.name: CoreProvider,
    DblpProvider.name: DblpProvider,
}


def register_provider(provider_cls: type[RetrievalProvider]) -> type[RetrievalProvider]:
    """Register a retrieval provider class by its ``name``."""
    _PROVIDER_CLASSES[provider_cls.name] = provider_cls
    return provider_cls


def get_provider_class(name: str) -> type[RetrievalProvider]:
    """Return the provider class registered under ``name``."""
    try:
        return _PROVIDER_CLASSES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown retrieval provider: {name}") from exc


def list_providers() -> list[str]:
    """Return registered provider names."""
    return sorted(_PROVIDER_CLASSES)


def create_provider(
    name: str,
    config: ProviderConfig | None = None,
) -> RetrievalProvider:
    """Instantiate a provider by name."""
    return get_provider_class(name)(config=config)


def get_enabled_providers(settings: AppSettings | None = None) -> list[RetrievalProvider]:
    """Return provider instances enabled in application settings."""
    from ...config.settings import get_settings

    resolved_settings = settings or get_settings()
    providers: list[RetrievalProvider] = []

    for name, provider_config in resolved_settings.retrieval.providers.items():
        if not provider_config.enabled:
            continue
        if name not in _PROVIDER_CLASSES:
            continue
        providers.append(create_provider(name, provider_config))

    return providers


async def health_check_enabled_providers(
    session: aiohttp.ClientSession,
    settings: AppSettings | None = None,
) -> list[ProviderHealth]:
    """Run health checks for all enabled providers."""
    providers = get_enabled_providers(settings)
    if not providers:
        return []

    return list(
        await asyncio.gather(*(provider.health_check(session) for provider in providers))
    )


async def search_enabled_providers(
    session: aiohttp.ClientSession,
    query: str,
    settings: AppSettings | None = None,
    limit: int | None = None,
) -> tuple[dict[str, list[RetrievedPaper]], list[str]]:
    """Search all enabled providers with graceful per-provider fallback."""
    providers = get_enabled_providers(settings)
    if not providers:
        return {}, ["No retrieval providers enabled"]

    async def _safe_search(
        provider: RetrievalProvider,
    ) -> tuple[str, list[RetrievedPaper], str | None]:
        try:
            papers = await provider.search(session, query, limit=limit)
            return provider.name, papers, None
        except Exception as exc:
            return provider.name, [], str(exc)

    results = await asyncio.gather(*(_safe_search(provider) for provider in providers))

    by_provider: dict[str, list[RetrievedPaper]] = {}
    warnings: list[str] = []
    for provider_name, papers, error in results:
        by_provider[provider_name] = papers
        if error:
            warnings.append(f"Provider '{provider_name}' failed for query '{query}': {error}")

    return by_provider, warnings


async def search_all_enabled(
    session: aiohttp.ClientSession,
    query: str,
    settings: AppSettings | None = None,
    limit: int | None = None,
) -> list[RetrievedPaper]:
    """Search all enabled providers and return a flat combined list."""
    by_provider, _warnings = await search_enabled_providers(
        session,
        query,
        settings=settings,
        limit=limit,
    )
    combined: list[RetrievedPaper] = []
    for papers in by_provider.values():
        combined.extend(papers)
    return combined
