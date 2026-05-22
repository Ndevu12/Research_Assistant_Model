# -*- coding: utf-8 -*-
"""Multi-provider retrieval stage with expanded query support."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import aiohttp

from ..core.context import PipelineContext, StageResult
from ..retrieval.models import ExpandedQuerySet, RetrievedPaper
from .providers.registry import get_enabled_providers

if TYPE_CHECKING:
    from ..config.settings import AppSettings


async def _search_query(
    session: aiohttp.ClientSession,
    query: str,
    settings: AppSettings,
) -> tuple[str, list[RetrievedPaper], list[str]]:
    """Search all enabled providers for a single query string."""
    warnings: list[str] = []
    providers = get_enabled_providers(settings)
    if not providers:
        warnings.append("No retrieval providers enabled")
        return query, [], warnings

    limit = settings.retrieval.per_provider_limit

    async def _safe_search(provider) -> tuple[str, list[RetrievedPaper]]:
        try:
            papers = await provider.search(session, query, limit=limit)
            return provider.name, papers
        except Exception as exc:
            warnings.append(f"Provider '{provider.name}' failed for query '{query}': {exc}")
            return provider.name, []

    results = await asyncio.gather(*(_safe_search(provider) for provider in providers))
    combined: list[RetrievedPaper] = []
    failed_providers: list[str] = []

    for provider_name, papers in results:
        if papers:
            updated: list[RetrievedPaper] = []
            for paper in papers:
                provenance = list(paper.raw_metadata.get("found_by_queries", []))
                if query not in provenance:
                    provenance.append(query)
                updated.append(
                    paper.model_copy(
                        update={
                            "raw_metadata": {
                                **paper.raw_metadata,
                                "found_by_queries": provenance,
                            }
                        }
                    )
                )
            combined.extend(updated)
        else:
            failed_providers.append(provider_name)

    return query, combined, warnings


async def retrieve_papers(
    expanded: ExpandedQuerySet,
    settings: AppSettings,
    session: aiohttp.ClientSession | None = None,
) -> tuple[list[RetrievedPaper], list[str]]:
    """Retrieve papers for the original query and expanded variants."""
    queries = [expanded.original, *expanded.variants]
    queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))

    concurrency = max(1, settings.retrieval.concurrency_limit)
    semaphore = asyncio.Semaphore(concurrency)
    all_warnings: list[str] = []

    async def _run_query(query: str) -> list[RetrievedPaper]:
        async with semaphore:
            if session is not None:
                _, papers, warnings = await _search_query(session, query, settings)
            else:
                async with aiohttp.ClientSession() as local_session:
                    _, papers, warnings = await _search_query(local_session, query, settings)
            all_warnings.extend(warnings)
            return papers

    batches = await asyncio.gather(*(_run_query(query) for query in queries))
    combined: list[RetrievedPaper] = []
    for papers in batches:
        combined.extend(papers)

    return combined, all_warnings


class RetrievalStage:
    """Pipeline stage that retrieves papers from enabled providers."""

    name = "retrieval"

    async def run(
        self,
        ctx: PipelineContext,
        data: ExpandedQuerySet,
    ) -> StageResult[list[RetrievedPaper]]:
        started = time.perf_counter()
        warnings: list[str] = []
        partial = False

        cached = ctx.get_artifact("cached_papers")
        if cached:
            papers = [RetrievedPaper.model_validate(item) for item in cached]
            ctx.set_artifact("retrieved_papers", papers)
            duration_ms = (time.perf_counter() - started) * 1000
            return StageResult(
                output=papers,
                duration_ms=duration_ms,
                metrics={
                    "papers_found": len(papers),
                    "providers_failed": [],
                    "cache_hit": True,
                },
                warnings=["Retrieval skipped: using cached papers"],
            )

        async with aiohttp.ClientSession() as session:
            try:
                papers, search_warnings = await retrieve_papers(data, ctx.config, session)
                warnings.extend(search_warnings)
            except Exception as exc:
                warnings.append(f"Retrieval failed: {exc}")
                papers = []
                partial = True

        if warnings:
            partial = True

        providers_failed = sorted(
            {
                warning.split("'")[1]
                for warning in warnings
                if warning.startswith("Provider '")
            }
        )
        ctx.metrics.record_retrieval(
            papers_found=len(papers),
            providers_failed=providers_failed,
        )
        ctx.set_artifact("retrieved_papers", papers)

        duration_ms = (time.perf_counter() - started) * 1000
        return StageResult(
            output=papers,
            duration_ms=duration_ms,
            metrics={
                "papers_found": len(papers),
                "providers_failed": providers_failed,
            },
            warnings=warnings,
            partial=partial,
        )
