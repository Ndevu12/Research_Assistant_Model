# -*- coding: utf-8 -*-
"""Unified report output rendering across markdown, JSON, and HTML."""

from __future__ import annotations

from ..retrieval.models import EnhancedResearchReport
from .html import render_html_report, render_pdf_ready_html
from .json_report import render_json_report
from .markdown import render_enhanced_markdown


def render_report_output(
    report: EnhancedResearchReport,
    *,
    output_format: str = "markdown",
    partial: bool = False,
    warnings: list[str] | None = None,
    export_formats: list[str] | None = None,
) -> str:
    """Render a report in the requested output format."""
    fmt = output_format.lower()
    if fmt == "json":
        return render_json_report(report, partial=partial, warnings=warnings or [])
    if fmt in {"html", "pdf"}:
        return render_html_report(
            report,
            partial=partial,
            warnings=warnings or [],
            pdf_ready=(fmt == "pdf"),
        )
    return render_enhanced_markdown(
        report,
        partial=partial,
        warnings=warnings,
        citation_index=report.citation_index,
        gap_analysis=report.gap_analysis,
    )
