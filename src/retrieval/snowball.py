# -*- coding: utf-8 -*-
"""Citation-graph snowballing over top-ranked papers.

After ranking, the highest-ranked papers seed a one-hop expansion of the
citation graph: their references (papers they cite) and citations (papers
that cite them) become new candidates, which are merged with the ranked
set, deduplicated, and re-ranked. Seminal work that keyword search misses
is usually one citation hop away from whatever search did find.

OpenAlex is the graph source: work objects retrieved during search already
carry ``referenced_works`` IDs in their raw metadata, so references cost a
single batched lookup, and citations use the ``cites:`` filter. Seeds from
other providers are resolved through their DOI when available.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import aiohttp

from ..core.context import PipelineContext, StageResult
from ..embeddings.base import EmbeddingProvider
from ..research.metadata_sanity import normalize_doi
from ..research.ranking import rank_papers
from ..research.embedding_context import store_ranking_embedding_result
from ..utils.logging_system import logger
from .deduplication import deduplicate_papers
from .models import RankedPaper, RetrievedPaper
from .providers.openalex import OpenAlexProvider

if TYPE_CHECKING:
    from ..config.settings import SnowballConfig

_WORKS_URL = "https://api.openalex.org/works"
_PROVENANCE_KEY = "found_by_queries"
_SNOWBALL_MARKER = "citation-snowball"


def _openalex_work_id(paper: RetrievedPaper) -> str | None:
    """Extract the bare OpenAlex work ID (``W...``) from a paper, if present."""
    raw_id = paper.raw_metadata.get("id")
    if isinstance(raw_id, str) and "openalex.org/W" in raw_id:
        return raw_id.rsplit("/", 1)[-1]
    if isinstance(raw_id, str) and raw_id.startswith("W"):
        return raw_id
    return None


def _reference_ids(paper: RetrievedPaper) -> list[str]:
    """Return bare OpenAlex IDs of works this paper references."""
    referenced = paper.raw_metadata.get("referenced_works")
    if not isinstance(referenced, list):
        return []
    return [str(item).rsplit("/", 1)[-1] for item in referenced if item]


def _mark_snowball(paper: RetrievedPaper) -> RetrievedPaper:
    provenance = list(paper.raw_metadata.get(_PROVENANCE_KEY, []))
    if _SNOWBALL_MARKER not in provenance:
        provenance.append(_SNOWBALL_MARKER)
    return paper.model_copy(
        update={"raw_metadata": {**paper.raw_metadata, _PROVENANCE_KEY: provenance}}
    )


async def _get_json(
    session: aiohttp.ClientSession,
    params: dict[str, str],
    timeout: int,
) -> dict:
    async with session.get(_WORKS_URL, params=params, timeout=timeout) as response:
        response.raise_for_status()
        return await response.json()


async def _resolve_seed(
    session: aiohttp.ClientSession,
    paper: RetrievedPaper,
    timeout: int,
) -> RetrievedPaper:
    """Return a seed enriched with OpenAlex graph fields, resolving by DOI if needed."""
    if _openalex_work_id(paper) is not None or not paper.doi:
        return paper
    doi = normalize_doi(paper.doi)
    try:
        data = await _get_json(session, {"filter": f"doi:{doi}", "per-page": "1"}, timeout)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return paper
    results = data.get("results") or []
    if not results:
        return paper
    resolved = results[0]
    return paper.model_copy(
        update={"raw_metadata": {**resolved, **paper.raw_metadata, "id": resolved.get("id")}}
    )


async def _fetch_works_by_ids(
    session: aiohttp.ClientSession,
    work_ids: list[str],
    timeout: int,
) -> list[RetrievedPaper]:
    """Batch-fetch works by OpenAlex ID (up to 50 per request)."""
    provider = OpenAlexProvider()
    papers: list[RetrievedPaper] = []
    for start in range(0, len(work_ids), 50):
        batch = work_ids[start : start + 50]
        data = await _get_json(
            session,
            {"filter": f"openalex_id:{'|'.join(batch)}", "per-page": str(len(batch))},
            timeout,
        )
        papers.extend(provider.normalize(item) for item in data.get("results", []))
    return papers


async def _fetch_citations(
    session: aiohttp.ClientSession,
    work_id: str,
    limit: int,
    timeout: int,
) -> list[RetrievedPaper]:
    """Fetch the most-cited works that cite ``work_id``."""
    provider = OpenAlexProvider()
    data = await _get_json(
        session,
        {
            "filter": f"cites:{work_id}",
            "per-page": str(limit),
            "sort": "cited_by_count:desc",
        },
        timeout,
    )
    return [provider.normalize(item) for item in data.get("results", [])]


async def collect_snowball_candidates(
    session: aiohttp.ClientSession,
    seeds: list[RetrievedPaper],
    config: SnowballConfig,
) -> list[RetrievedPaper]:
    """One-hop citation-graph expansion around the seed papers."""
    timeout = config.request_timeout_seconds

    resolved = await asyncio.gather(
        *(_resolve_seed(session, seed, timeout) for seed in seeds)
    )

    reference_ids: list[str] = []
    seen_ids: set[str] = set()
    for seed in resolved:
        for ref_id in _reference_ids(seed):
            if ref_id not in seen_ids:
                seen_ids.add(ref_id)
                reference_ids.append(ref_id)
    reference_ids = reference_ids[: config.max_reference_fetch]

    citation_tasks = [
        _fetch_citations(session, work_id, config.per_seed_citations, timeout)
        for work_id in (_openalex_work_id(seed) for seed in resolved)
        if work_id is not None
    ]

    async def _safe(coro) -> list[RetrievedPaper]:
        try:
            return await coro
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning("Snowball fetch failed: %s", exc)
            return []

    batches = await asyncio.gather(
        _safe(_fetch_works_by_ids(session, reference_ids, timeout)),
        *(_safe(task) for task in citation_tasks),
    )

    candidates = [paper for batch in batches for paper in batch]
    return [_mark_snowball(paper) for paper in candidates[: config.max_new_papers]]


class SnowballStage:
    """Pipeline stage that expands the ranked set via the citation graph."""

    name = "snowball"

    def __init__(self, embedder: EmbeddingProvider | None = None) -> None:
        self.embedder = embedder

    async def run(
        self,
        ctx: PipelineContext,
        data: list[RankedPaper],
    ) -> StageResult[list[RankedPaper]]:
        started = time.perf_counter()
        config = ctx.config.snowball

        def _passthrough(warnings: list[str], **metrics: object) -> StageResult[list[RankedPaper]]:
            return StageResult(
                output=data,
                duration_ms=(time.perf_counter() - started) * 1000,
                metrics={"papers_added": 0, **metrics},
                warnings=warnings,
            )

        if not config.enabled or not data:
            return _passthrough([], skipped=True)

        seeds = [ranked.paper for ranked in data[: config.max_seed_papers]]
        try:
            async with aiohttp.ClientSession() as session:
                candidates = await collect_snowball_candidates(session, seeds, config)
        except Exception as exc:
            return _passthrough([f"Citation snowballing failed: {exc}"])

        if not candidates:
            return _passthrough([], candidates_fetched=0)

        embedder = self.embedder
        if embedder is None:
            from ..embeddings import try_create_embedding_provider

            embedder = try_create_embedding_provider(ctx.config.embedding)

        base_papers = [ranked.paper for ranked in data]
        try:
            combined, dedup_stats = deduplicate_papers(
                base_papers + candidates,
                config=ctx.config.deduplication,
                embedder=embedder,
            )
            ranking_result = rank_papers(
                papers=combined,
                query=ctx.query,
                config=ctx.config.ranking,
                embedder=embedder,
            )
        except ImportError:
            # Embedding backend unavailable at runtime; keyword-only fallback.
            combined, dedup_stats = deduplicate_papers(
                base_papers + candidates,
                config=ctx.config.deduplication.model_copy(
                    update={"enable_embedding_dedup": False}
                ),
                embedder=None,
            )
            ranking_result = rank_papers(
                papers=combined,
                query=ctx.query,
                config=ctx.config.ranking,
                embedder=None,
            )
        ranked = ranking_result.ranked
        store_ranking_embedding_result(
            ctx,
            ranking_result.query_embedding,
            ranking_result.paper_embeddings,
        )

        base_titles = {paper.title for paper in base_papers}
        papers_added = sum(1 for item in ranked if item.paper.title not in base_titles)

        ctx.set_artifact("ranked_papers", ranked)

        return StageResult(
            output=ranked,
            duration_ms=(time.perf_counter() - started) * 1000,
            metrics={
                "seeds_used": len(seeds),
                "candidates_fetched": len(candidates),
                "duplicates_removed": dedup_stats["metadata_removed"]
                + dedup_stats["embedding_removed"],
                "papers_added": papers_added,
                "papers_ranked": len(ranked),
            },
        )
