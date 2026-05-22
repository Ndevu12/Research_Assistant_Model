# -*- coding: utf-8 -*-
"""Report generation and export formats."""

from .citations import (
    CitationExportStage,
    build_citation_index,
    format_bibtex_entry,
    generate_bibtex,
    make_citation_key,
)
from .html import render_html_report
from .json_report import render_json_report, report_to_dict
from .markdown import render_enhanced_markdown, render_markdown
from .output import render_report_output
from .report_generation import ReportGenerationStage, assemble_report

__all__ = [
    "CitationExportStage",
    "ReportGenerationStage",
    "assemble_report",
    "build_citation_index",
    "format_bibtex_entry",
    "generate_bibtex",
    "make_citation_key",
    "render_enhanced_markdown",
    "render_html_report",
    "render_json_report",
    "render_markdown",
    "render_report_output",
    "report_to_dict",
]
