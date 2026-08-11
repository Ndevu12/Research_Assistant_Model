# -*- coding: utf-8 -*-
"""Shared query and paper embedding artifacts for pipeline stages."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ..embeddings.base import cosine_similarity

if TYPE_CHECKING:
    from ..core.context import PipelineContext
    from ..retrieval.models import RankedPaper, RetrievedPaper

__all__ = [
    "cosine_similarity",
    "store_ranking_embedding_result",
    "store_embedding_artifacts",
    "get_query_embedding",
    "get_paper_embeddings",
    "get_paper_embedding",
    "resolve_paper_embedding_matrix",
]

QUERY_EMBEDDING_KEY = "query_embedding"
PAPER_EMBEDDINGS_KEY = "paper_embeddings"


def store_ranking_embedding_result(
    ctx: PipelineContext,
    query_embedding: np.ndarray | None,
    paper_embeddings: dict[str, np.ndarray] | None,
) -> None:
    """Persist ranking embeddings on the pipeline context for downstream reuse."""
    if query_embedding is not None:
        ctx.set_artifact(QUERY_EMBEDDING_KEY, query_embedding)
    if paper_embeddings:
        ctx.set_artifact(PAPER_EMBEDDINGS_KEY, paper_embeddings)


def store_embedding_artifacts(
    ctx: PipelineContext,
    query_embedding: np.ndarray | None,
    papers: list[RetrievedPaper],
    paper_vectors: list[np.ndarray | None],
) -> None:
    """Persist ranking embeddings on the pipeline context for downstream reuse."""
    if query_embedding is not None:
        ctx.set_artifact(QUERY_EMBEDDING_KEY, query_embedding)

    paper_embeddings: dict[str, np.ndarray] = {}
    for paper, vector in zip(papers, paper_vectors, strict=True):
        if vector is not None:
            paper_embeddings[paper.paper_id] = vector

    if paper_embeddings:
        ctx.set_artifact(PAPER_EMBEDDINGS_KEY, paper_embeddings)


def get_query_embedding(ctx: PipelineContext) -> np.ndarray | None:
    """Return the cached query embedding, if ranking produced one."""
    value = ctx.get_artifact(QUERY_EMBEDDING_KEY)
    if value is None:
        return None
    return np.asarray(value)


def get_paper_embeddings(ctx: PipelineContext) -> dict[str, np.ndarray]:
    """Return cached paper embeddings keyed by paper_id."""
    value = ctx.get_artifact(PAPER_EMBEDDINGS_KEY)
    if not value:
        return {}
    return {paper_id: np.asarray(vector) for paper_id, vector in value.items()}


def get_paper_embedding(ctx: PipelineContext, paper_id: str) -> np.ndarray | None:
    """Return a single cached paper embedding by paper_id."""
    vector = get_paper_embeddings(ctx).get(paper_id)
    if vector is None:
        return None
    return vector


def resolve_paper_embedding_matrix(
    ranked_papers: list[RankedPaper],
    paper_embeddings: dict[str, np.ndarray] | None,
) -> np.ndarray | None:
    """Build an embedding matrix aligned with ranked_papers when cache is complete."""
    if not paper_embeddings or not ranked_papers:
        return None

    vectors: list[np.ndarray] = []
    for ranked in ranked_papers:
        vector = paper_embeddings.get(ranked.paper.paper_id)
        if vector is None:
            return None
        vectors.append(np.asarray(vector))

    return np.vstack(vectors)
