# -*- coding: utf-8 -*-
"""Tests for multi-provider retrieval and provider failure fallbacks."""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import patch

import aiohttp
import pytest

from src.config.settings import AppSettings, ProviderConfig
from src.core.context import PipelineContext
from src.core.pipeline import ResearchPipeline
from src.retrieval.models import ExpandedQuerySet, RetrievedPaper
from src.retrieval.providers.base import RetrievalProvider
from src.retrieval.retrieval_stage import RetrievalStage, _search_query, retrieve_papers


def _paper(title: str, provider: str = "openalex") -> RetrievedPaper:
    return RetrievedPaper(title=title, provider=provider)


class SuccessProvider(RetrievalProvider):
    name: ClassVar[str] = "success_provider"

    def __init__(self, papers: list[RetrievedPaper] | None = None) -> None:
        super().__init__(ProviderConfig())
        self._papers = papers or [_paper("Success Paper", provider=self.name)]

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        return self._papers

    def normalize(self, raw: dict) -> RetrievedPaper:
        return RetrievedPaper(title=str(raw.get("title", "Unknown")), provider=self.name)


class FailingProvider(RetrievalProvider):
    name: ClassVar[str] = "failing_provider"

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        raise RuntimeError("provider unavailable")

    def normalize(self, raw: dict) -> RetrievedPaper:
        return RetrievedPaper(title="unused", provider=self.name)


class EmptyProvider(RetrievalProvider):
    name: ClassVar[str] = "empty_provider"

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        return []

    def normalize(self, raw: dict) -> RetrievedPaper:
        return RetrievedPaper(title="unused", provider=self.name)


@pytest.mark.asyncio
async def test_search_query_continues_when_one_provider_fails() -> None:
    settings = AppSettings()
    providers = [
        FailingProvider(),
        SuccessProvider([_paper("OpenAlex Paper", provider="success_provider")]),
    ]

    async with aiohttp.ClientSession() as session:
        with patch(
            "src.retrieval.providers.registry.get_enabled_providers",
            return_value=providers,
        ):
            query, papers, warnings, failed = await _search_query(
                session, "transformers", settings
            )

    assert query == "transformers"
    assert len(papers) == 1
    assert papers[0].title == "OpenAlex Paper"
    assert any("failing_provider" in warning for warning in warnings)
    assert failed == {"failing_provider"}


@pytest.mark.asyncio
async def test_search_query_returns_empty_when_all_providers_fail() -> None:
    settings = AppSettings()
    providers = [FailingProvider(), FailingProvider()]

    async with aiohttp.ClientSession() as session:
        with patch(
            "src.retrieval.providers.registry.get_enabled_providers",
            return_value=providers,
        ):
            _, papers, warnings, failed = await _search_query(session, "biology", settings)

    assert papers == []
    assert len(warnings) == 2
    assert failed == {"failing_provider"}


@pytest.mark.asyncio
async def test_retrieve_papers_merges_successful_provider_results() -> None:
    settings = AppSettings()
    expanded = ExpandedQuerySet(original="machine learning", variants=[])
    providers = [
        SuccessProvider([_paper("Paper A", provider="success_provider")]),
        FailingProvider(),
    ]

    async with aiohttp.ClientSession() as session:
        with patch(
            "src.retrieval.providers.registry.get_enabled_providers",
            return_value=providers,
        ):
            papers, warnings, providers_failed = await retrieve_papers(
                expanded, settings, session
            )

    assert len(papers) == 1
    assert papers[0].title == "Paper A"
    assert warnings
    assert providers_failed == ["failing_provider"]


@pytest.mark.asyncio
async def test_retrieval_stage_marks_partial_when_provider_fails() -> None:
    settings = AppSettings()
    expanded = ExpandedQuerySet(original="NLP transformers", variants=[])
    ctx = PipelineContext.create("NLP transformers", settings)
    stage = RetrievalStage()
    providers = [
        SuccessProvider([_paper("Recovered Paper")]),
        FailingProvider(),
    ]

    with patch(
        "src.retrieval.providers.registry.get_enabled_providers",
        return_value=providers,
    ):
        result = await stage.run(ctx, expanded)

    assert result.partial is True
    assert len(result.output) == 1
    assert result.output[0].title == "Recovered Paper"
    assert "failing_provider" in result.metrics["providers_failed"]
    assert ctx.metrics.retrieval_papers_found == 1


@pytest.mark.asyncio
async def test_retrieval_stage_not_partial_when_all_providers_succeed() -> None:
    settings = AppSettings()
    expanded = ExpandedQuerySet(original="graph neural networks", variants=[])
    ctx = PipelineContext.create("graph neural networks", settings)
    stage = RetrievalStage()
    providers = [
        SuccessProvider([_paper("Paper One")]),
        SuccessProvider([_paper("Paper Two")]),
    ]

    with patch(
        "src.retrieval.providers.registry.get_enabled_providers",
        return_value=providers,
    ):
        result = await stage.run(ctx, expanded)

    assert result.partial is False
    assert len(result.output) == 2
    assert result.metrics["providers_failed"] == []


@pytest.mark.asyncio
async def test_pipeline_continues_after_retrieval_provider_failure() -> None:
    settings = AppSettings(
        pipeline={
            "enabled_stages": {
                "query_expansion": True,
                "retrieval": True,
                "post_retrieval": True,
            }
        }
    )
    providers = [
        FailingProvider(),
        SuccessProvider([_paper("Pipeline Paper")]),
    ]

    class QueryExpansionStub:
        name = "query_expansion"

        async def run(self, ctx: PipelineContext, data: object) -> object:
            from src.core.context import StageResult

            return StageResult(
                output=ExpandedQuerySet(original=str(data), variants=[]),
                duration_ms=1.0,
            )

    class PostRetrievalStage:
        name = "post_retrieval"

        async def run(self, ctx: PipelineContext, data: object) -> object:
            from src.core.context import StageResult

            assert isinstance(data, list)
            assert len(data) == 1
            return StageResult(output=f"processed:{len(data)}", duration_ms=1.0)

    with patch(
        "src.retrieval.providers.registry.get_enabled_providers",
        return_value=providers,
    ):
        pipeline = ResearchPipeline(
            [QueryExpansionStub(), RetrievalStage(), PostRetrievalStage()],
            settings,
        )
        result = await pipeline.execute("continuity query")

    assert result.partial is True
    assert "retrieval" in result.stage_results
    assert result.stage_results["retrieval"]["partial"] is True
    assert "post_retrieval" in result.stage_results
    assert result.output == "processed:1"
