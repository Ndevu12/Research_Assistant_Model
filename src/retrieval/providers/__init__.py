# -*- coding: utf-8 -*-
"""Retrieval providers and registry."""

from .arxiv import ArxivProvider
from .base import ProviderHealth, RetrievalProvider
from .core_provider import CoreProvider
from .crossref import CrossRefProvider
from .dblp import DblpProvider
from .openalex import OpenAlexProvider
from .pubmed import PubMedProvider
from .registry import (
    create_provider,
    get_enabled_providers,
    get_provider_class,
    health_check_enabled_providers,
    list_providers,
    register_provider,
    search_all_enabled,
    search_enabled_providers,
)
from .semantic_scholar import SemanticScholarProvider

__all__ = [
    "ArxivProvider",
    "CoreProvider",
    "CrossRefProvider",
    "DblpProvider",
    "OpenAlexProvider",
    "ProviderHealth",
    "PubMedProvider",
    "RetrievalProvider",
    "SemanticScholarProvider",
    "create_provider",
    "get_enabled_providers",
    "get_provider_class",
    "health_check_enabled_providers",
    "list_providers",
    "register_provider",
    "search_all_enabled",
    "search_enabled_providers",
]
