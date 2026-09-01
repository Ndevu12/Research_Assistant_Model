# -*- coding: utf-8 -*-
"""Ranking-quality metrics for the evaluation harness."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of relevant items that appear in the top ``k`` results."""
    if not relevant_ids:
        return 0.0
    top = set(ranked_ids[:k])
    return len(top & relevant_ids) / len(relevant_ids)


def ndcg_at_k(ranked_ids: Sequence[str], relevance: Mapping[str, int], k: int) -> float:
    """Normalized discounted cumulative gain with graded relevance labels."""
    gains = [relevance.get(item_id, 0) for item_id in ranked_ids[:k]]
    dcg = sum(gain / math.log2(position + 2) for position, gain in enumerate(gains))

    ideal_gains = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum(gain / math.log2(position + 2) for position, gain in enumerate(ideal_gains))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def mrr(ranked_ids: Sequence[str], relevant_ids: set[str]) -> float:
    """Reciprocal rank of the first relevant result."""
    for position, item_id in enumerate(ranked_ids, start=1):
        if item_id in relevant_ids:
            return 1.0 / position
    return 0.0
