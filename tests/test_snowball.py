# -*- coding: utf-8 -*-
"""Tests for citation-graph snowballing."""

from __future__ import annotations

from unittest.mock import patch

import aiohttp
import pytest

from src.config.settings import AppSettings, SnowballConfig
from src.core.context import PipelineContext
from src.retrieval.models import RankedPaper, RetrievedPaper
from src.retrieval.snowball import (
    SnowballStage,
    _openalex_work_id,
    _reference_ids,
    collect_snowball_candidates,
)


def _openalex_work(work_id: str, title: str, referenced: list[str] | None = None) -> dict:
    return {
        "id": f"https://openalex.org/{work_id}",
        "display_name": title,
        "publication_year": 2020,
        "cited_by_count": 10,
        "referenced_works": [f"https://openalex.org/{ref}" for ref in (referenced or [])],
    }


def _paper(title: str, work_id: str | None = None, referenced: list[str] | None = None) -> RetrievedPaper:
    raw = _openalex_work(work_id, title, referenced) if work_id else {}
    return RetrievedPaper(title=title, provider="openalex", year=2020, raw_metadata=raw)


def _ranked(paper: RetrievedPaper, score: float = 0.8) -> RankedPaper:
    return RankedPaper(paper=paper, rank_score=score, score_breakdown={})


def test_work_id_and_reference_extraction() -> None:
    paper = _paper("Seed", work_id="W1", referenced=["W2", "W3"])
    assert _openalex_work_id(paper) == "W1"
    assert _reference_ids(paper) == ["W2", "W3"]

    bare = RetrievedPaper(title="No graph data", provider="semantic_scholar")
    assert _openalex_work_id(bare) is None
    assert _reference_ids(bare) == []


async def test_collect_candidates_fetches_references_and_citations() -> None:
    seeds = [_paper("Seed", work_id="W1", referenced=["W2", "W3"])]
    config = SnowballConfig(per_seed_citations=2, max_new_papers=10)

    async def fake_get_json(session, params, timeout):
        if params.get("filter", "").startswith("openalex_id:"):
            return {"results": [_openalex_work("W2", "Referenced Paper")]}
        if params.get("filter", "").startswith("cites:"):
            return {"results": [_openalex_work("W9", "Citing Paper")]}
        return {"results": []}

    with patch("src.retrieval.snowball._get_json", side_effect=fake_get_json):
        async with aiohttp.ClientSession() as session:
            candidates = await collect_snowball_candidates(session, seeds, config)

    titles = {paper.title for paper in candidates}
    assert titles == {"Referenced Paper", "Citing Paper"}
    for paper in candidates:
        assert "citation-snowball" in paper.raw_metadata["found_by_queries"]


async def test_collect_candidates_respects_max_new_papers() -> None:
    seeds = [_paper("Seed", work_id="W1", referenced=["W2", "W3", "W4"])]
    config = SnowballConfig(per_seed_citations=3, max_new_papers=2)

    async def fake_get_json(session, params, timeout):
        if params.get("filter", "").startswith("openalex_id:"):
            return {
                "results": [
                    _openalex_work("W2", "Ref A"),
                    _openalex_work("W3", "Ref B"),
                    _openalex_work("W4", "Ref C"),
                ]
            }
        return {"results": [_openalex_work("W9", "Citing Paper")]}

    with patch("src.retrieval.snowball._get_json", side_effect=fake_get_json):
        async with aiohttp.ClientSession() as session:
            candidates = await collect_snowball_candidates(session, seeds, config)

    assert len(candidates) == 2


async def test_stage_passthrough_when_disabled() -> None:
    settings = AppSettings(snowball={"enabled": False})
    ctx = PipelineContext.create("test query", settings)
    ranked = [_ranked(_paper("Seed", work_id="W1"))]

    result = await SnowballStage().run(ctx, ranked)

    assert result.output == ranked
    assert result.metrics["papers_added"] == 0


async def test_stage_merges_new_candidates_into_ranking() -> None:
    settings = AppSettings(
        snowball={"enabled": True},
        deduplication={"enable_embedding_dedup": False},
    )
    ctx = PipelineContext.create("graph neural networks", settings)
    seed = _paper("Graph Neural Networks Survey", work_id="W1")
    ranked = [_ranked(seed)]

    new_candidate = RetrievedPaper(
        title="Semi-Supervised Classification with Graph Convolutional Networks",
        provider="openalex",
        year=2017,
        abstract="Graph convolutional networks for semi-supervised node classification.",
        raw_metadata={"found_by_queries": ["citation-snowball"]},
    )

    async def fake_collect(session, seeds, config):
        return [new_candidate]

    with patch("src.retrieval.snowball.collect_snowball_candidates", side_effect=fake_collect):
        result = await SnowballStage(embedder=None).run(ctx, ranked)

    titles = {item.paper.title for item in result.output}
    assert "Semi-Supervised Classification with Graph Convolutional Networks" in titles
    assert "Graph Neural Networks Survey" in titles
    assert result.metrics["papers_added"] == 1
    assert result.metrics["candidates_fetched"] == 1
    assert ctx.get_artifact("ranked_papers") == result.output


async def test_stage_degrades_gracefully_on_network_failure() -> None:
    settings = AppSettings(snowball={"enabled": True})
    ctx = PipelineContext.create("test query", settings)
    ranked = [_ranked(_paper("Seed", work_id="W1"))]

    async def failing_collect(session, seeds, config):
        raise aiohttp.ClientError("network down")

    with patch("src.retrieval.snowball.collect_snowball_candidates", side_effect=failing_collect):
        result = await SnowballStage().run(ctx, ranked)

    assert result.output == ranked
    assert any("snowballing failed" in warning.lower() for warning in result.warnings)


async def test_stage_deduplicates_candidates_already_in_ranked_set() -> None:
    settings = AppSettings(
        snowball={"enabled": True},
        deduplication={"enable_embedding_dedup": False},
    )
    ctx = PipelineContext.create("test query", settings)
    seed = _paper("Existing Paper", work_id="W1")
    ranked = [_ranked(seed)]

    duplicate = RetrievedPaper(title="Existing Paper", provider="openalex", year=2020)

    async def fake_collect(session, seeds, config):
        return [duplicate]

    with patch("src.retrieval.snowball.collect_snowball_candidates", side_effect=fake_collect):
        result = await SnowballStage(embedder=None).run(ctx, ranked)

    assert len(result.output) == 1
    assert result.metrics["papers_added"] == 0
    assert result.metrics["duplicates_removed"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
