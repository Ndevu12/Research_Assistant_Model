# -*- coding: utf-8 -*-
"""Rendering functions for the retrieval module."""

from .models import ResearchReport


def render_markdown(report: ResearchReport) -> str:
    """Render a research report as markdown."""
    lines = ["# Research helper results\n", f"Query: {report.query}\n"]
    for i, p in enumerate(report.papers, start=1):
        meta = [str(p.year) if p.year else "", p.venue or ""]
        meta_str = " | ".join(m for m in meta if m)
        lines.append(f"## {i}. {p.title}")
        if meta_str:
            lines.append(meta_str)
        if p.url:
            lines.append(f"Source: {p.url}")
        elif p.doi:
            lines.append(f"Source: {p.doi}")
        else:
            lines.append("Source: (not provided)")
        if p.key_points:
            lines.append("\nKey points:")
            lines.extend(f"- {b}" for b in p.key_points)
        if p.why_relevant:
            lines.append("\nWhy this matches your query:")
            lines.extend(f"- {b}" for b in p.why_relevant)
        lines.append("\n")
    return "\n".join(lines)
