# -*- coding: utf-8 -*-
"""Cross-encoder reranking of the top-ranked papers.

The ranking stage is a fast first pass (bi-encoder embeddings plus weighted
signals). A cross-encoder reads the query and each paper *together*, which is
substantially more accurate but too slow for the full candidate pool — so it
reranks only the top of the list, the standard two-stage retrieval pattern.

The cross-encoder score is blended with the first-pass rank score rather
than replacing it, so citation, recency, and venue signals keep influencing
the final order. The backend (``sentence-transformers``) is optional: when
unavailable, the stage passes the original ranking through with a warning.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Protocol

from ..core.context import PipelineContext, StageResult
from ..retrieval.models import RankedPaper
from ..utils.logging_system import logger

if TYPE_CHECKING:
    from ..config.settings import RerankConfig


class RerankScorer(Protocol):
    """Scores query/document pairs; higher means more relevant."""

    def score(self, query: str, documents: list[str]) -> list[float]: ...


class CrossEncoderScorer:
    """Cross-encoder scorer backed by sentence-transformers."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
        return self._model

    def score(self, query: str, documents: list[str]) -> list[float]:
        model = self._load()
        predictions = model.predict([(query, document) for document in documents])
        return [float(value) for value in predictions]


def try_create_reranker(config: RerankConfig) -> CrossEncoderScorer | None:
    """Create the cross-encoder scorer, or None when the backend is missing."""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return None
    return CrossEncoderScorer(config.model)


def _paper_document(paper: RankedPaper) -> str:
    parts = [paper.paper.title]
    if paper.paper.abstract:
        parts.append(paper.paper.abstract[:1000])
    return " ".join(parts)


def _min_max_normalize(values: list[float]) -> list[float]:
    lowest, highest = min(values), max(values)
    spread = highest - lowest
    if spread == 0:
        return [0.5] * len(values)
    return [(value - lowest) / spread for value in values]


class RerankStage:
    """Pipeline stage that reranks the top papers with a cross-encoder."""

    name = "rerank"

    def __init__(self, scorer: RerankScorer | None = None) -> None:
        self.scorer = scorer

    async def run(
        self,
        ctx: PipelineContext,
        data: list[RankedPaper],
    ) -> StageResult[list[RankedPaper]]:
        started = time.perf_counter()
        config = ctx.config.rerank

        def _passthrough(warnings: list[str], **metrics: object) -> StageResult[list[RankedPaper]]:
            return StageResult(
                output=data,
                duration_ms=(time.perf_counter() - started) * 1000,
                metrics={"papers_reranked": 0, **metrics},
                warnings=warnings,
            )

        if not config.enabled or len(data) < 2:
            return _passthrough([], skipped=True)

        scorer = self.scorer or try_create_reranker(config)
        if scorer is None:
            return _passthrough(
                [
                    "Cross-encoder reranking skipped: sentence-transformers is "
                    "not installed. Run: pipenv install"
                ]
            )

        head = data[: config.top_n]
        tail = data[config.top_n :]
        documents = [_paper_document(paper) for paper in head]

        try:
            raw_scores = await asyncio.to_thread(scorer.score, ctx.query, documents)
        except Exception as exc:
            logger.warning("Cross-encoder reranking failed: %s", exc)
            return _passthrough([f"Cross-encoder reranking failed: {exc}"])

        normalized = _min_max_normalize(raw_scores)
        blend = config.blend_weight

        reranked = [
            paper.model_copy(
                update={
                    "rank_score": round(
                        blend * ce_score + (1 - blend) * paper.rank_score, 4
                    ),
                    "score_breakdown": {
                        **paper.score_breakdown,
                        "cross_encoder_score": round(ce_score, 4),
                        "pre_rerank_score": paper.rank_score,
                    },
                }
            )
            for paper, ce_score in zip(head, normalized, strict=True)
        ]
        reranked.sort(key=lambda item: item.rank_score, reverse=True)

        output = reranked + tail
        ctx.set_artifact("ranked_papers", output)

        return StageResult(
            output=output,
            duration_ms=(time.perf_counter() - started) * 1000,
            metrics={
                "papers_reranked": len(reranked),
                "model": scorer.model_name if hasattr(scorer, "model_name") else "custom",
            },
        )
