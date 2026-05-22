# -*- coding: utf-8 -*-
"""Helpers for normalizing pipeline stage data across degraded runs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..retrieval.models import RankedPaper, RetrievedPaper

if TYPE_CHECKING:
    from ..config.settings import RankingConfig


def ensure_ranked_papers(
    data: list[RankedPaper] | list[RetrievedPaper] | list[object],
    query: str,
    config: RankingConfig | None = None,
) -> tuple[list[RankedPaper], list[str]]:
    """Coerce pipeline data into ranked papers, recovering when ranking failed."""
    warnings: list[str] = []

    if not data:
        return [], warnings

    if isinstance(data[0], RankedPaper):
        return data, warnings  # type: ignore[return-value]

    if isinstance(data[0], RetrievedPaper):
        warnings.append(
            "Ranking stage did not produce RankedPaper output; "
            "falling back to keyword-only ranking"
        )
        from ..research.ranking import rank_papers

        ranked = rank_papers(
            papers=data,  # type: ignore[arg-type]
            query=query,
            config=config,
            embedder=None,
        )
        return ranked, warnings

    warnings.append("Unexpected pipeline data type; returning empty ranked list")
    return [], warnings
