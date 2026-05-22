# -*- coding: utf-8 -*-
"""Query understanding stage for intent, constraints, and key concepts."""

from __future__ import annotations

import re
import time

from ..core.context import PipelineContext, StageResult
from ..retrieval.models import QueryUnderstandingResult
from .query_expansion import extract_core_concepts


def understand_query(query: str) -> QueryUnderstandingResult:
    """Derive structured query understanding from the raw user query."""
    key_concepts = extract_core_concepts(query)
    constraints: dict[str, object] = {}

    year_matches = [int(match) for match in re.findall(r"\b(19|20)\d{2}\b", query)]
    if year_matches:
        constraints["years"] = sorted(set(year_matches))

    after_match = re.search(r"\bafter\s+(19|20\d{2})\b", query, flags=re.IGNORECASE)
    if after_match:
        constraints["min_year"] = int(after_match.group(1))

    before_match = re.search(r"\bbefore\s+(19|20\d{2})\b", query, flags=re.IGNORECASE)
    if before_match:
        constraints["max_year"] = int(before_match.group(1))

    intent = "literature_review"
    if re.search(r"\bcompare\b|\bcomparison\b|\bversus\b|\bvs\.?\b", query, flags=re.IGNORECASE):
        intent = "comparison"
    elif re.search(r"\bgap\b|\bopportunit", query, flags=re.IGNORECASE):
        intent = "gap_analysis"

    return QueryUnderstandingResult(
        intent=intent,
        constraints=constraints,
        key_concepts=key_concepts,
    )


class QueryUnderstandingStage:
    """Pipeline stage that extracts intent, constraints, and key concepts."""

    name = "query_understanding"

    async def run(
        self,
        ctx: PipelineContext,
        data: str,
    ) -> StageResult[QueryUnderstandingResult]:
        started = time.perf_counter()
        query = str(data) if data else ctx.query
        result = understand_query(query)
        ctx.set_artifact("query_understanding", result)

        duration_ms = (time.perf_counter() - started) * 1000
        return StageResult(
            output=result,
            duration_ms=duration_ms,
            metrics={
                "intent": result.intent,
                "concept_count": len(result.key_concepts),
            },
        )
