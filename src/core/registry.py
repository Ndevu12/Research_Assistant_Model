# -*- coding: utf-8 -*-
"""Central plugin registry for retrieval providers, pipeline stages, and extensions."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from ..retrieval.providers.base import RetrievalProvider

T = TypeVar("T")
Factory = Callable[..., T]


class PluginRegistry:
    """Register and resolve pluggable components across the research pipeline."""

    def __init__(self) -> None:
        self._retrieval_providers: dict[str, type[RetrievalProvider]] = {}
        self._pipeline_stages: dict[str, Factory[Any]] = {}
        self._fulltext_downloaders: dict[str, Factory[Any]] = {}
        self._fulltext_indexes: dict[str, Factory[Any]] = {}

    # -- Retrieval providers -------------------------------------------------

    def register_retrieval_provider(
        self,
        provider_cls: type[RetrievalProvider],
    ) -> type[RetrievalProvider]:
        """Register a retrieval provider class by its ``name``."""
        self._retrieval_providers[provider_cls.name] = provider_cls
        return provider_cls

    def get_retrieval_provider_class(self, name: str) -> type[RetrievalProvider]:
        try:
            return self._retrieval_providers[name]
        except KeyError as exc:
            raise KeyError(f"Unknown retrieval provider: {name}") from exc

    def list_retrieval_providers(self) -> list[str]:
        return sorted(self._retrieval_providers)

    def create_retrieval_provider(self, name: str, **kwargs: Any) -> RetrievalProvider:
        return self.get_retrieval_provider_class(name)(**kwargs)

    # -- Pipeline stages -----------------------------------------------------

    def register_stage(self, name: str, factory: Factory[Any]) -> None:
        """Register a factory that builds a pipeline stage under ``name``."""
        self._pipeline_stages[name] = factory

    def get_stage_factory(self, name: str) -> Factory[Any]:
        try:
            return self._pipeline_stages[name]
        except KeyError as exc:
            raise KeyError(f"Unknown pipeline stage: {name}") from exc

    def list_stages(self) -> list[str]:
        return sorted(self._pipeline_stages)

    def create_stage(self, name: str, **kwargs: Any) -> Any:
        return self.get_stage_factory(name)(**kwargs)

    # -- Full-text extensions ------------------------------------------------

    def register_fulltext_downloader(self, name: str, factory: Factory[Any]) -> None:
        self._fulltext_downloaders[name] = factory

    def register_fulltext_index(self, name: str, factory: Factory[Any]) -> None:
        self._fulltext_indexes[name] = factory

    def list_fulltext_downloaders(self) -> list[str]:
        return sorted(self._fulltext_downloaders)

    def list_fulltext_indexes(self) -> list[str]:
        return sorted(self._fulltext_indexes)


_global_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Return the process-wide plugin registry."""
    return _global_registry


def register_retrieval_provider(
    provider_cls: type[RetrievalProvider],
) -> type[RetrievalProvider]:
    """Register a retrieval provider in the global registry."""
    from ..retrieval.providers.registry import register_provider

    register_provider(provider_cls)
    return _global_registry.register_retrieval_provider(provider_cls)


def register_stage(name: str, factory: Factory[Any]) -> None:
    """Register a pipeline stage factory in the global registry."""
    _global_registry.register_stage(name, factory)


def bootstrap_default_plugins() -> None:
    """Load built-in providers and stages into the global registry."""
    from ..analysis.gap_analysis import GapAnalysisStage
    from ..analysis.synthesis import SynthesisStage
    from ..reporting.citations import CitationExportStage
    from ..reporting.report_generation import ReportGenerationStage
    from ..research.clustering import ClusteringStage
    from ..research.query_expansion import QueryExpansionStage
    from ..research.query_understanding import QueryUnderstandingStage
    from ..research.ranking import RankingStage
    from ..research.relevance_scoring import RelevanceScoringStage
    from ..retrieval.deduplication import DeduplicationStage
    from ..retrieval.providers.arxiv import ArxivProvider
    from ..retrieval.providers.core_provider import CoreProvider
    from ..retrieval.providers.crossref import CrossRefProvider
    from ..retrieval.providers.dblp import DblpProvider
    from ..retrieval.providers.openalex import OpenAlexProvider
    from ..retrieval.providers.pubmed import PubMedProvider
    from ..retrieval.providers.registry import register_provider
    from ..retrieval.providers.semantic_scholar import SemanticScholarProvider
    from ..retrieval.retrieval_stage import RetrievalStage

    builtin_providers: list[type[RetrievalProvider]] = [
        OpenAlexProvider,
        SemanticScholarProvider,
        ArxivProvider,
        CrossRefProvider,
        PubMedProvider,
        CoreProvider,
        DblpProvider,
    ]
    for provider_cls in builtin_providers:
        register_provider(provider_cls)
        _global_registry.register_retrieval_provider(provider_cls)

    stage_factories: dict[str, Factory[Any]] = {
        "query_understanding": QueryUnderstandingStage,
        "query_expansion": QueryExpansionStage,
        "retrieval": RetrievalStage,
        "deduplication": DeduplicationStage,
        "ranking": RankingStage,
        "relevance_scoring": RelevanceScoringStage,
        "clustering": ClusteringStage,
        "synthesis": SynthesisStage,
        "gap_analysis": GapAnalysisStage,
        "citation_export": CitationExportStage,
        "report_generation": ReportGenerationStage,
    }
    for name, factory in stage_factories.items():
        _global_registry.register_stage(name, factory)

    from ..fulltext.downloader import CachingPDFDownloader
    from ..fulltext.rag import InMemoryFulltextIndex

    _global_registry.register_fulltext_downloader("default", CachingPDFDownloader)
    _global_registry.register_fulltext_index("default", InMemoryFulltextIndex)
