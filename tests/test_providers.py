# -*- coding: utf-8 -*-
"""Tests for retrieval provider registry and normalization."""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from src.config.settings import AppSettings, ProviderConfig
from src.retrieval.models import RetrievedPaper
from src.retrieval.providers import (
    ArxivProvider,
    CrossRefProvider,
    OpenAlexProvider,
    SemanticScholarProvider,
    create_provider,
    get_enabled_providers,
    get_provider_class,
    health_check_enabled_providers,
    list_providers,
    register_provider,
    search_enabled_providers,
)
from src.retrieval.providers.base import RetrievalProvider


class TestProviderRegistry:
    def test_builtin_providers_registered(self) -> None:
        names = list_providers()

        assert "openalex" in names
        assert "semantic_scholar" in names
        assert "arxiv" in names
        assert "crossref" in names
        assert "pubmed" in names
        assert "core" in names
        assert "dblp" in names

    def test_create_provider_uses_config_limit(self) -> None:
        provider = create_provider("openalex", ProviderConfig(limit=12))

        assert isinstance(provider, OpenAlexProvider)
        assert provider.resolve_limit(None) == 12

    def test_get_enabled_providers_respects_yaml_defaults(self) -> None:
        settings = AppSettings.from_yaml()
        providers = get_enabled_providers(settings)
        names = {provider.name for provider in providers}

        assert names == {"openalex", "semantic_scholar"}

    def test_get_enabled_providers_includes_optional_sources_when_enabled(self) -> None:
        settings = AppSettings.from_yaml(
            retrieval={
                "providers": {
                    "openalex": {"enabled": True, "limit": 8},
                    "semantic_scholar": {"enabled": False, "limit": 8},
                    "arxiv": {"enabled": True, "limit": 5},
                    "crossref": {"enabled": True, "limit": 5},
                }
            }
        )
        providers = get_enabled_providers(settings)
        names = {provider.name for provider in providers}

        assert names == {"openalex", "arxiv", "crossref"}

    def test_get_enabled_providers_skips_disabled(self) -> None:
        settings = AppSettings.from_yaml(
            retrieval={
                "providers": {
                    "openalex": {"enabled": True, "limit": 8},
                    "semantic_scholar": {"enabled": False, "limit": 8},
                }
            }
        )
        providers = get_enabled_providers(settings)

        assert len(providers) == 1
        assert providers[0].name == "openalex"

    def test_register_provider_extends_registry(self) -> None:
        class StubProvider(RetrievalProvider):
            name = "stub_provider"

            async def search(self, session, query, limit=None):
                return []

            def normalize(self, raw: dict) -> RetrievedPaper:
                return RetrievedPaper(title="Stub", provider=self.name)

        register_provider(StubProvider)

        assert get_provider_class("stub_provider") is StubProvider


class FailingRegistryProvider(RetrievalProvider):
    name: ClassVar[str] = "failing_registry_provider"

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        raise RuntimeError("provider unavailable")

    def normalize(self, raw: dict) -> RetrievedPaper:
        return RetrievedPaper(title="unused", provider=self.name)


class SuccessRegistryProvider(RetrievalProvider):
    name: ClassVar[str] = "success_registry_provider"

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        return [RetrievedPaper(title="Recovered", provider=self.name)]

    def normalize(self, raw: dict) -> RetrievedPaper:
        return RetrievedPaper(title="unused", provider=self.name)


@pytest.mark.asyncio
async def test_search_enabled_providers_falls_back_when_one_provider_fails() -> None:
    settings = AppSettings()
    providers = [FailingRegistryProvider(), SuccessRegistryProvider()]

    async with aiohttp.ClientSession() as session:
        with patch(
            "src.retrieval.providers.registry.get_enabled_providers",
            return_value=providers,
        ):
            by_provider, warnings, failed = await search_enabled_providers(
                session,
                "transformers",
                settings=settings,
            )

    assert by_provider["success_registry_provider"][0].title == "Recovered"
    assert by_provider["failing_registry_provider"] == []
    assert any("failing_registry_provider" in warning for warning in warnings)
    assert failed == {"failing_registry_provider"}


@pytest.mark.asyncio
async def test_health_check_enabled_providers_reports_status() -> None:
    class HealthyProvider(RetrievalProvider):
        name: ClassVar[str] = "healthy_provider"

        async def search(self, session, query, limit=None):
            return []

        def normalize(self, raw: dict) -> RetrievedPaper:
            return RetrievedPaper(title="unused", provider=self.name)

        async def _ping(self, session: aiohttp.ClientSession) -> bool:
            return True

    class UnhealthyProvider(RetrievalProvider):
        name: ClassVar[str] = "unhealthy_provider"

        async def search(self, session, query, limit=None):
            return []

        def normalize(self, raw: dict) -> RetrievedPaper:
            return RetrievedPaper(title="unused", provider=self.name)

        async def _ping(self, session: aiohttp.ClientSession) -> bool:
            raise RuntimeError("offline")

    providers = [HealthyProvider(), UnhealthyProvider()]

    async with aiohttp.ClientSession() as session:
        with patch(
            "src.retrieval.providers.registry.get_enabled_providers",
            return_value=providers,
        ):
            results = await health_check_enabled_providers(session)

    by_name = {result.provider: result for result in results}
    assert by_name["healthy_provider"].healthy is True
    assert by_name["unhealthy_provider"].healthy is False
    assert "offline" in by_name["unhealthy_provider"].message


@pytest.mark.asyncio
async def test_arxiv_health_check_uses_lightweight_query() -> None:
    provider = ArxivProvider()
    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_get = AsyncMock()
    mock_get.__aenter__.return_value = mock_response
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.get.return_value = mock_get

    result = await provider.health_check(mock_session)

    assert result.healthy is True
    mock_session.get.assert_called_once()
    _, kwargs = mock_session.get.call_args
    assert kwargs["params"]["max_results"] == "1"


@pytest.mark.asyncio
async def test_crossref_health_check_uses_lightweight_query() -> None:
    provider = CrossRefProvider()
    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_get = AsyncMock()
    mock_get.__aenter__.return_value = mock_response
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.get.return_value = mock_get

    result = await provider.health_check(mock_session)

    assert result.healthy is True
    mock_session.get.assert_called_once()
    _, kwargs = mock_session.get.call_args
    assert kwargs["params"]["rows"] == "1"


class TestProviderNormalization:
    def test_openalex_normalize_maps_core_fields(self) -> None:
        provider = OpenAlexProvider()
        paper = provider.normalize(
            {
                "display_name": "Attention Is All You Need",
                "publication_year": 2017,
                "doi": "https://doi.org/10.1234/test",
                "cited_by_count": 90000,
                "id": "https://openalex.org/W123",
                "primary_location": {
                    "source": {"display_name": "NeurIPS"},
                    "landing_page_url": "https://example.com/paper",
                },
                "abstract_inverted_index": {"attention": [0], "mechanisms": [1]},
            }
        )

        assert paper.title == "Attention Is All You Need"
        assert paper.year == 2017
        assert paper.venue == "NeurIPS"
        assert paper.provider == "openalex"
        assert paper.citation_count == 90000
        assert paper.abstract == "attention mechanisms"

    def test_semantic_scholar_normalize_maps_doi(self) -> None:
        provider = SemanticScholarProvider()
        paper = provider.normalize(
            {
                "title": "BERT",
                "abstract": "Pre-training summary.",
                "year": 2019,
                "venue": "NAACL",
                "url": "https://example.com/bert",
                "externalIds": {"DOI": "10.1234/bert"},
            }
        )

        assert paper.title == "BERT"
        assert paper.provider == "semantic_scholar"
        assert paper.doi == "https://doi.org/10.1234/bert"

    def test_arxiv_normalize_maps_core_fields(self) -> None:
        provider = ArxivProvider()
        paper = provider.normalize(
            {
                "id": "http://arxiv.org/abs/1706.03762v5",
                "title": "Attention Is All You Need",
                "summary": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
                "published": "2017-06-12T00:00:00Z",
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
                "primary_category": "cs.CL",
                "doi": "10.1234/arxiv-example",
            }
        )

        assert paper.title == "Attention Is All You Need"
        assert paper.year == 2017
        assert paper.provider == "arxiv"
        assert paper.venue == "cs.CL"
        assert paper.doi == "https://doi.org/10.1234/arxiv-example"
        assert paper.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert paper.url == "http://arxiv.org/abs/1706.03762v5"

    def test_crossref_normalize_maps_core_fields(self) -> None:
        provider = CrossRefProvider()
        paper = provider.normalize(
            {
                "title": ["Deep Residual Learning for Image Recognition"],
                "abstract": "<jats:p>We present a residual learning framework.</jats:p>",
                "published-print": {"date-parts": [[2016, 6, 26]]},
                "container-title": ["CVPR"],
                "DOI": "10.1109/CVPR.2016.90",
                "URL": "https://doi.org/10.1109/CVPR.2016.90",
                "is-referenced-by-count": 120000,
                "author": [
                    {"given": "Kaiming", "family": "He"},
                    {"given": "Xiangyu", "family": "Zhang"},
                ],
            }
        )

        assert paper.title == "Deep Residual Learning for Image Recognition"
        assert paper.year == 2016
        assert paper.provider == "crossref"
        assert paper.venue == "CVPR"
        assert paper.doi == "https://doi.org/10.1109/CVPR.2016.90"
        assert paper.citation_count == 120000
        assert paper.authors == ["Kaiming He", "Xiangyu Zhang"]
        assert paper.abstract == "We present a residual learning framework."

    def test_arxiv_search_query_preserves_field_syntax(self) -> None:
        provider = ArxivProvider()

        assert provider._search_query("ti:attention") == "ti:attention"
        assert provider._search_query("transformer models") == "all:transformer models"
