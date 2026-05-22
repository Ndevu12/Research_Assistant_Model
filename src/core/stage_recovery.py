# -*- coding: utf-8 -*-
"""Stage output recovery when pipeline stages time out or fail."""

from __future__ import annotations

from typing import Any

from .context import PipelineContext


def recover_stage_output(stage_name: str, ctx: PipelineContext, data: Any) -> Any:
    """Return a typed fallback output for a failed or timed-out stage."""
    if stage_name == "synthesis":
        from ..analysis.synthesis import recover_synthesis_output

        clusters = data if isinstance(data, list) else ctx.get_artifact("paper_clusters") or []
        return recover_synthesis_output(ctx, clusters)

    if stage_name == "gap_analysis":
        from ..analysis.gap_analysis import recover_gap_analysis_output

        return recover_gap_analysis_output(ctx, data)

    return data
