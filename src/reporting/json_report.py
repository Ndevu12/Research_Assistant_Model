# -*- coding: utf-8 -*-
"""JSON report serialization."""

from __future__ import annotations

import json
from typing import Any

from ..retrieval.models import EnhancedResearchReport


def report_to_dict(
    report: EnhancedResearchReport,
    *,
    partial: bool = False,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Convert an enhanced report to a JSON-serializable dictionary."""
    payload = report.model_dump(mode="json")
    payload["meta"] = {
        "partial": partial,
        "warnings": warnings or [],
        "paper_count": len(report.papers),
        "cluster_count": len(report.clusters),
    }
    return payload


def render_json_report(
    report: EnhancedResearchReport,
    *,
    partial: bool = False,
    warnings: list[str] | None = None,
    indent: int = 2,
) -> str:
    """Render an enhanced research report as formatted JSON."""
    return json.dumps(
        report_to_dict(report, partial=partial, warnings=warnings),
        indent=indent,
        ensure_ascii=False,
    )
