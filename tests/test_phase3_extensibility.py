# -*- coding: utf-8 -*-
"""Tests for Phase 3 extensibility: stubs, registry, events, API, PDF HTML."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import aiohttp
import pytest

from src.config.settings import AppSettings
from src.core.context import PipelineContext, StageResult
from src.core.events import StageEventCollector
from src.core.pipeline import ResearchPipeline
from src.core.registry import bootstrap_default_plugins, get_registry
from src.fulltext.downloader import StubPDFDownloader
from src.fulltext.rag import StubRAGIndex
from src.reporting.html import render_pdf_ready_html
from src.reporting.output import render_report_output
from src.retrieval.providers import (
    CoreProvider,
    DblpProvider,
    PubMedProvider,
    create_provider,
    list_providers,
)


class NamedEchoStage:
    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, ctx: PipelineContext, data: Any) -> StageResult[Any]:
        return StageResult(output=f"{self.name}:{data}", duration_ms=1.0)


class TestPhase3ProviderStubs:
    def test_stub_providers_registered(self) -> None:
        names = list_providers()

        assert "pubmed" in names
        assert "core" in names
        assert "dblp" in names

    def test_stub_providers_disabled_by_default(self) -> None:
        settings = AppSettings.from_yaml()
        enabled = {
            name
            for name, cfg in settings.retrieval.providers.items()
            if cfg.enabled
        }

        assert "pubmed" not in enabled
        assert "core" not in enabled
        assert "dblp" not in enabled

    @pytest.mark.parametrize(
        ("provider_name", "provider_cls"),
        [
            ("pubmed", PubMedProvider),
            ("core", CoreProvider),
            ("dblp", DblpProvider),
        ],
    )
    def test_create_stub_provider(self, provider_name: str, provider_cls: type) -> None:
        provider = create_provider(provider_name)
        assert isinstance(provider, provider_cls)

    def test_pubmed_normalize_maps_ncbi_fields(self) -> None:
        provider = PubMedProvider()
        paper = provider.normalize(
            {
                "uid": "12345678",
                "title": "Sample PubMed Article",
                "abstract": "An example abstract.",
                "pubdate": "2024 Jan",
                "source": "Journal of Examples",
                "doi": "10.1000/pubmed-sample",
                "AuthorList": [
                    {"LastName": "Smith", "ForeName": "Jane"},
                ],
            }
        )

        assert paper.title == "Sample PubMed Article"
        assert paper.year == 2024
        assert paper.provider == "pubmed"
        assert paper.doi == "https://doi.org/10.1000/pubmed-sample"
        assert paper.url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
        assert paper.authors == ["Smith Jane"]

    def test_core_normalize_maps_api_fields(self) -> None:
        provider = CoreProvider()
        paper = provider.normalize(
            {
                "title": "Open Access Paper",
                "abstract": "Full text available.",
                "year": 2023,
                "doi": "10.1000/core-sample",
                "authors": ["Ada Lovelace"],
                "downloadUrl": "https://core.ac.uk/download/pdf/123.pdf",
                "citationCount": 42,
            }
        )

        assert paper.title == "Open Access Paper"
        assert paper.year == 2023
        assert paper.provider == "core"
        assert paper.citation_count == 42
        assert paper.url == "https://core.ac.uk/download/pdf/123.pdf"

    def test_dblp_normalize_maps_json_fields(self) -> None:
        provider = DblpProvider()
        paper = provider.normalize(
            {
                "title": "Efficient Algorithms.",
                "author": [
                    {"@pid": "h/1", "text": "Alice Author"},
                    {"@pid": "h/2", "text": "Bob Author"},
                ],
                "info": {
                    "year": 2022,
                    "venue": "SODA",
                    "doi": "10.1000/dblp-sample",
                },
                "url": "https://dblp.org/rec/conf/soda/2022/example",
            }
        )

        assert paper.title == "Efficient Algorithms"
        assert paper.year == 2022
        assert paper.provider == "dblp"
        assert paper.venue == "SODA"
        assert paper.authors == ["Alice Author", "Bob Author"]

    @pytest.mark.asyncio
    async def test_stub_provider_search_raises_not_implemented(self) -> None:
        provider = PubMedProvider()

        async with aiohttp.ClientSession() as session:
            with pytest.raises(NotImplementedError, match="PubMed"):
                await provider.search(session, "cancer immunotherapy")

    @pytest.mark.asyncio
    async def test_stub_provider_health_check_reports_unavailable(self) -> None:
        provider = DblpProvider()

        async with aiohttp.ClientSession() as session:
            health = await provider.health_check(session)

        assert health.healthy is False
        assert health.provider == "dblp"
        assert "not yet implemented" in health.message.lower()


class TestFullTextScaffold:
    @pytest.mark.asyncio
    async def test_stub_pdf_downloader_not_implemented(self) -> None:
        downloader = StubPDFDownloader()

        with pytest.raises(NotImplementedError, match="PDF download"):
            await downloader.download("paper-1", "https://example.com/paper.pdf")

    @pytest.mark.asyncio
    async def test_stub_rag_index_not_implemented(self) -> None:
        index = StubRAGIndex()

        with pytest.raises(NotImplementedError, match="RAG indexing"):
            await index.index_chunks([])


class TestPluginRegistry:
    def test_bootstrap_registers_builtin_providers_and_stages(self) -> None:
        bootstrap_default_plugins()

        global_registry = get_registry()
        providers = global_registry.list_retrieval_providers()
        stages = global_registry.list_stages()

        assert "pubmed" in providers
        assert "core" in providers
        assert "dblp" in providers
        assert "query_understanding" in stages
        assert "report_generation" in stages
        assert "stub" in global_registry.list_fulltext_downloaders()
        assert "stub" in global_registry.list_fulltext_indexes()

    def test_registry_create_retrieval_provider(self) -> None:
        bootstrap_default_plugins()
        provider = get_registry().create_retrieval_provider("pubmed")

        assert isinstance(provider, PubMedProvider)


class TestPipelineEvents:
    @pytest.mark.asyncio
    async def test_stage_events_fire_during_pipeline(self) -> None:
        collector = StageEventCollector()
        bus = collector.attach()

        pipeline = ResearchPipeline(
            [NamedEchoStage("alpha"), NamedEchoStage("beta")],
            AppSettings(),
            event_bus=bus,
        )
        await pipeline.execute("event test query")

        started_names = [name for name, _ in collector.started]
        completed_names = [name for name, _ in collector.completed]

        assert started_names == ["alpha", "beta"]
        assert completed_names == ["alpha", "beta"]


class TestPdfReadyHtml:
    def test_render_pdf_ready_html_includes_print_rules(self) -> None:
        from tests.test_reporting import _sample_report

        html = render_pdf_ready_html(_sample_report())

        assert 'class="pdf-ready"' in html
        assert "@page" in html
        assert "size: A4" in html
        assert "break-inside: avoid-page" in html

    def test_render_report_output_pdf_format(self) -> None:
        from tests.test_reporting import _sample_report

        html = render_report_output(_sample_report(), output_format="pdf")

        assert "@page" in html
        assert 'class="pdf-ready"' in html


class TestApiScaffold:
    def test_create_app_requires_fastapi(self) -> None:
        from src.api.app import create_app

        with patch.dict("sys.modules", {"fastapi": None}):
            with pytest.raises(ImportError, match="FastAPI"):
                create_app()

    def test_create_app_when_fastapi_available(self) -> None:
        pytest.importorskip("fastapi")
        from src.api.app import create_app

        app = create_app(AppSettings())
        assert app.title == "Research Assistant API"
