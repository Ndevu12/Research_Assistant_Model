# -*- coding: utf-8 -*-
"""Multi-provider retrieval stage with expanded query support."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import aiohttp

from ..core.context import PipelineContext, StageResult
from ..retrieval.models import ExpandedQuerySet, RetrievedPaper
from .providers.registry import search_enabled_providers

if TYPE_CHECKING:
    from ..config.settings import AppSettings


async def _search_query(
    session: aiohttp.ClientSession,
    query: str,
    settings: AppSettings,
) -> tuple[str, list[RetrievedPaper], list[str], set[str]]:
    """Search all enabled providers for a single query string."""
    by_provider, warnings, failed_providers = await search_enabled_providers(
        session,
        query,
        settings=settings,
        limit=settings.retrieval.per_provider_limit,
    )

    combined: list[RetrievedPaper] = []
    for papers in by_provider.values():
        for paper in papers:
            provenance = list(paper.raw_metadata.get("found_by_queries", []))
            if query not in provenance:
                provenance.append(query)
            combined.append(
                paper.model_copy(
                    update={
                        "raw_metadata": {
                            **paper.raw_metadata,
                            "found_by_queries": provenance,
                        }
                    }
                )
            )

    return query, combined, warnings, failed_providers


async def retrieve_papers(
    expanded: ExpandedQuerySet,
    settings: AppSettings,
    session: aiohttp.ClientSession | None = None,
) -> tuple[list[RetrievedPaper], list[str], list[str]]:
    """Retrieve papers for the original query and expanded variants.

    Returns the combined papers, accumulated warnings, and the sorted names of
    providers that raised at least one error.
    """
    queries = [expanded.original, *expanded.variants]
    queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))

    concurrency = max(1, settings.retrieval.concurrency_limit)
    semaphore = asyncio.Semaphore(concurrency)
    all_warnings: list[str] = []
    all_failed: set[str] = set()

    async def _run_query(query: str) -> list[RetrievedPaper]:
        async with semaphore:
            if session is not None:
                _, papers, warnings, failed = await _search_query(session, query, settings)
            else:
                async with aiohttp.ClientSession() as local_session:
                    _, papers, warnings, failed = await _search_query(
                        local_session, query, settings
                    )
            all_warnings.extend(warnings)
            all_failed.update(failed)
            return papers

    batches = await asyncio.gather(*(_run_query(query) for query in queries))
    combined: list[RetrievedPaper] = []
    for papers in batches:
        combined.extend(papers)

    return combined, all_warnings, sorted(all_failed)


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

        providers_failed: list[str] = []
        async with aiohttp.ClientSession() as session:
            try:
                papers, search_warnings, providers_failed = await retrieve_papers(
                    data, ctx.config, session
                )
                warnings.extend(search_warnings)
            except Exception as exc:
                warnings.append(f"Retrieval failed: {exc}")
                papers = []
                partial = True

        if warnings:
            partial = True

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
