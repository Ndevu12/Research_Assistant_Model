# -*- coding: utf-8 -*-
"""Citation key generation and export pipeline stage."""

from __future__ import annotations

import time

from ..core.context import PipelineContext, StageResult
from ..export import SUPPORTED_FORMATS, generate_citation_exports
from ..export.bibtex import build_citation_index, format_bibtex_entry, generate_bibtex, make_citation_key
from ..retrieval.models import GapAnalysisResult, RankedPaper

__all__ = [
    "CitationExportStage",
    "build_citation_index",
    "format_bibtex_entry",
    "generate_bibtex",
    "make_citation_key",
]


class CitationExportStage:
    """Pipeline stage that generates citation exports from ranked papers."""

    name = "citation_export"

    async def run(
        self,
        ctx: PipelineContext,
        data: GapAnalysisResult,
    ) -> StageResult[dict[str, str]]:
        started = time.perf_counter()

        ranked_papers: list[RankedPaper] = ctx.get_artifact("ranked_papers") or []
        papers = [item.paper for item in ranked_papers]
        citation_index = build_citation_index(papers)
        exports = generate_citation_exports(papers, formats=list(SUPPORTED_FORMATS))

        ctx.set_artifact("citation_exports", exports)
        ctx.set_artifact("citation_index", citation_index)

        duration_ms = (time.perf_counter() - started) * 1000
        return StageResult(
            output=exports,
            duration_ms=duration_ms,
            metrics={"citation_count": len(citation_index)},
        )
