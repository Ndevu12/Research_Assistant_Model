# -*- coding: utf-8 -*-
"""Enhanced markdown report rendering with thematic sections."""

from __future__ import annotations

from typing import Mapping

from ..retrieval.models import (
    EnhancedResearchReport,
    GapAnalysisResult,
    PaperAnalysis,
    PaperCluster,
    ResearchReport,
    SynthesisResult,
)


def _bullet_lines(items: list[str], indent: str = "") -> list[str]:
    if not items:
        return [f"{indent}_None identified._"]
    return [f"{indent}- {item}" for item in items]


def _format_paper_source(paper: PaperAnalysis) -> str:
    if paper.url:
        return paper.url
    if paper.doi:
        return paper.doi
    return "(not provided)"


def _lookup_paper(
    paper_id: str,
    analyses: list[PaperAnalysis],
    by_id: Mapping[str, PaperAnalysis],
) -> PaperAnalysis | None:
    if paper_id in by_id:
        return by_id[paper_id]
    for analysis in analyses:
        if analysis.paper_id == paper_id or analysis.title == paper_id:
            return analysis
    return None


def _render_thematic_findings(
    clusters: list[PaperCluster],
    analyses: list[PaperAnalysis],
    by_id: Mapping[str, PaperAnalysis],
    citation_index: Mapping[str, str],
) -> list[str]:
    if not clusters:
        return ["_No thematic clusters were generated._"]

    lines: list[str] = []
    for index, cluster in enumerate(clusters, start=1):
        lines.append(f"## Theme {index}: {cluster.theme}")
        if cluster.summary:
            lines.append(cluster.summary)
        lines.append("")

        if not cluster.paper_ids:
            lines.append("_No papers assigned to this theme._")
            lines.append("")
            continue

        for paper_id in cluster.paper_ids:
            paper = _lookup_paper(paper_id, analyses, by_id)
            cite_key = citation_index.get(paper_id, "")
            cite_suffix = f" [{cite_key}]" if cite_key else ""
            if paper is None:
                lines.append(f"- {paper_id}{cite_suffix}")
                continue

            meta_parts = [part for part in (str(paper.year) if paper.year else "", paper.venue or "") if part]
            meta = " | ".join(meta_parts)
            lines.append(f"### {paper.title}{cite_suffix}")
            if meta:
                lines.append(meta)
            lines.append(f"Source: {_format_paper_source(paper)}")
            if paper.key_points:
                lines.extend(["", "Key points:", *_bullet_lines(paper.key_points)])
            if paper.why_relevant:
                lines.extend(["", "Why relevant:", *_bullet_lines(paper.why_relevant)])
            if paper.evidence:
                lines.extend(
                    [
                        "",
                        "Evidence (from full text):",
                        *[f"> {quote}" for quote in paper.evidence],
                    ]
                )
            lines.append("")

    return lines


def _render_appendix(
    analyses: list[PaperAnalysis],
    citation_index: Mapping[str, str],
) -> list[str]:
    if not analyses:
        return ["_No papers retrieved._"]

    lines: list[str] = []
    for index, paper in enumerate(analyses, start=1):
        cite_key = ""
        if paper.paper_id and paper.paper_id in citation_index:
            cite_key = f" [{citation_index[paper.paper_id]}]"
        lines.append(f"## {index}. {paper.title}{cite_key}")
        meta_parts = [part for part in (str(paper.year) if paper.year else "", paper.venue or "") if part]
        if meta_parts:
            lines.append(" | ".join(meta_parts))
        lines.append(f"Source: {_format_paper_source(paper)}")
        if paper.key_points:
            lines.extend(["", "Key points:", *_bullet_lines(paper.key_points)])
        lines.append("")
    return lines


def render_enhanced_markdown(
    report: EnhancedResearchReport,
    *,
    partial: bool = False,
    warnings: list[str] | None = None,
    citation_index: Mapping[str, str] | None = None,
    gap_analysis: GapAnalysisResult | None = None,
) -> str:
    """Render an enhanced research report as markdown with thematic sections."""
    resolved_warnings = warnings or []
    resolved_index = citation_index if citation_index is not None else report.citation_index
    resolved_gap_analysis = gap_analysis if gap_analysis is not None else report.gap_analysis

    lines: list[str] = ["# Research Report", ""]

    if partial or resolved_warnings:
        lines.extend(["## Pipeline Notice", ""])
        if partial:
            lines.append(
                "_This report was generated with partial pipeline results. "
                "Some stages may have failed or timed out._"
            )
        if resolved_warnings:
            lines.extend(["", "Warnings:", *_bullet_lines(resolved_warnings)])
        lines.append("")

    lines.extend(["# Executive Summary", ""])
    if report.executive_summary:
        lines.append(report.executive_summary)
    else:
        lines.append(f"Literature review for: **{report.query}**")
    lines.append("")

    lines.extend(["# Research Query & Scope", "", f"**Query:** {report.query}", ""])

    lines.extend(["# Thematic Findings", ""])
    index = resolved_index
    by_id = {analysis.paper_id: analysis for analysis in report.papers if analysis.paper_id}
    lines.extend(_render_thematic_findings(report.clusters, report.papers, by_id, index))

    synthesis: SynthesisResult | None = report.synthesis
    lines.extend(["# Methodology Comparison", ""])
    if synthesis and synthesis.methodologies:
        lines.extend(_bullet_lines(synthesis.methodologies))
    else:
        lines.append("_No cross-paper methodology synthesis available._")
    lines.append("")

    lines.extend(["# Key Datasets & Benchmarks", ""])
    datasets = list(synthesis.datasets) if synthesis else []
    lines.extend(_bullet_lines(datasets))
    lines.append("")

    lines.extend(["# Trends & Timeline", ""])
    timeline = report.timeline or (synthesis.trends if synthesis else [])
    lines.extend(_bullet_lines(timeline))
    lines.append("")

    lines.extend(["# Agreements & Disagreements", ""])
    if synthesis:
        if synthesis.agreements:
            lines.extend(["## Agreements", "", *_bullet_lines(synthesis.agreements), ""])
        if synthesis.disagreements:
            lines.extend(["## Disagreements", "", *_bullet_lines(synthesis.disagreements), ""])
    if not synthesis or (not synthesis.agreements and not synthesis.disagreements):
        lines.append("_No agreement/disagreement analysis available._")
        lines.append("")

    lines.extend(["# Research Gaps & Opportunities", ""])
    gap_items = list(report.gaps)
    opportunity_items: list[str] = []
    if resolved_gap_analysis:
        opportunity_items = list(resolved_gap_analysis.opportunities)
        if resolved_gap_analysis.underexplored_areas:
            gap_items.extend(resolved_gap_analysis.underexplored_areas)
    elif synthesis:
        gap_items.extend(synthesis.gaps)

    if gap_items:
        lines.extend(["## Gaps", "", *_bullet_lines(list(dict.fromkeys(gap_items))), ""])
    if opportunity_items:
        lines.extend(["## Opportunities", "", *_bullet_lines(opportunity_items), ""])
    if not gap_items and not opportunity_items:
        lines.append("_No research gaps identified._")
        lines.append("")

    lines.extend(["# References", ""])
    if index:
        for paper_id, cite_key in sorted(index.items(), key=lambda item: item[1]):
            paper = by_id.get(paper_id)
            title = paper.title if paper else paper_id
            lines.append(f"- [{cite_key}] {title}")
    elif report.papers:
        for paper in report.papers:
            lines.append(f"- {paper.title}")
    else:
        lines.append("_No references available._")
    lines.append("")

    if report.exports.get("bibtex"):
        lines.extend(["## BibTeX", "", "```bibtex", report.exports["bibtex"], "```", ""])

    lines.extend(["# Appendix: All Papers", ""])
    lines.extend(_render_appendix(report.papers, index))

    return "\n".join(lines).rstrip() + "\n"


def render_markdown(report: ResearchReport) -> str:
    """Render a legacy research report as simple markdown."""
    lines = ["# Research helper results\n", f"Query: {report.query}\n"]
    for index, paper in enumerate(report.papers, start=1):
        meta = [str(paper.year) if paper.year else "", paper.venue or ""]
        meta_str = " | ".join(part for part in meta if part)
        lines.append(f"## {index}. {paper.title}")
        if meta_str:
            lines.append(meta_str)
        lines.append(f"Source: {_format_paper_source(paper)}")
        if paper.key_points:
            lines.extend(["", "Key points:", *_bullet_lines(paper.key_points)])
        if paper.why_relevant:
            lines.extend(["", "Why this matches your query:", *_bullet_lines(paper.why_relevant)])
        lines.append("")
    return "\n".join(lines)
