# -*- coding: utf-8 -*-
"""HTML report rendering with print-friendly styling."""

from __future__ import annotations

import html
from typing import Mapping

from ..retrieval.models import EnhancedResearchReport, GapAnalysisResult, PaperAnalysis, SynthesisResult


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _render_list(items: list[str]) -> str:
    if not items:
        return "<p><em>None identified.</em></p>"
    rows = "".join(f"<li>{_esc(item)}</li>" for item in items)
    return f"<ul>{rows}</ul>"


def render_html_report(
    report: EnhancedResearchReport,
    *,
    partial: bool = False,
    warnings: list[str] | None = None,
    pdf_ready: bool = False,
) -> str:
    """Render an enhanced research report as standalone HTML.

    When ``pdf_ready`` is True, additional print CSS is included for clean
    PDF export via the browser print dialog or headless Chromium.
    """
    resolved_warnings = warnings or []
    synthesis: SynthesisResult | None = report.synthesis
    gap_analysis: GapAnalysisResult | None = report.gap_analysis

    body_parts: list[str] = [
        f"<h1>{_esc('Research Report')}</h1>",
    ]

    if partial or resolved_warnings:
        body_parts.append("<section class='notice'>")
        body_parts.append("<h2>Pipeline Notice</h2>")
        if partial:
            body_parts.append(
                "<p><em>This report was generated with partial pipeline results.</em></p>"
            )
        if resolved_warnings:
            body_parts.append(_render_list(resolved_warnings))
        body_parts.append("</section>")

    body_parts.extend(
        [
            "<section>",
            "<h2>Executive Summary</h2>",
            f"<p>{_esc(report.executive_summary or report.query)}</p>",
            "</section>",
            "<section>",
            "<h2>Research Query &amp; Scope</h2>",
            f"<p><strong>Query:</strong> {_esc(report.query)}</p>",
            "</section>",
        ]
    )

    body_parts.append("<section><h2>Thematic Findings</h2>")
    if report.clusters:
        for index, cluster in enumerate(report.clusters, start=1):
            body_parts.append(f"<h3>Theme {index}: {_esc(cluster.theme)}</h3>")
            if cluster.summary:
                body_parts.append(f"<p>{_esc(cluster.summary)}</p>")
            if cluster.paper_ids:
                body_parts.append("<ul>")
                by_id = {p.paper_id: p for p in report.papers if p.paper_id}
                for paper_id in cluster.paper_ids:
                    paper = by_id.get(paper_id)
                    label = paper.title if paper else paper_id
                    cite = report.citation_index.get(paper_id, "")
                    suffix = f" [{_esc(cite)}]" if cite else ""
                    body_parts.append(f"<li>{_esc(label)}{suffix}</li>")
                body_parts.append("</ul>")
    else:
        body_parts.append("<p><em>No thematic clusters were generated.</em></p>")
    body_parts.append("</section>")

    body_parts.extend(
        [
            "<section><h2>Methodology Comparison</h2>",
            _render_list(list(synthesis.methodologies) if synthesis else []),
            "</section>",
            "<section><h2>Key Datasets &amp; Benchmarks</h2>",
            _render_list(list(synthesis.datasets) if synthesis else []),
            "</section>",
            "<section><h2>Trends &amp; Timeline</h2>",
            _render_list(report.timeline or (list(synthesis.trends) if synthesis else [])),
            "</section>",
        ]
    )

    body_parts.append("<section><h2>Agreements &amp; Disagreements</h2>")
    if synthesis:
        if synthesis.agreements:
            body_parts.append("<h3>Agreements</h3>" + _render_list(list(synthesis.agreements)))
        if synthesis.disagreements:
            body_parts.append("<h3>Disagreements</h3>" + _render_list(list(synthesis.disagreements)))
    if not synthesis or (not synthesis.agreements and not synthesis.disagreements):
        body_parts.append("<p><em>No agreement/disagreement analysis available.</em></p>")
    body_parts.append("</section>")

    body_parts.append("<section><h2>Research Gaps &amp; Opportunities</h2>")
    gaps = list(report.gaps)
    opportunities: list[str] = []
    if gap_analysis:
        opportunities = list(gap_analysis.opportunities)
        gaps.extend(gap_analysis.underexplored_areas)
    elif synthesis:
        gaps.extend(synthesis.gaps)
    if gaps:
        body_parts.append("<h3>Gaps</h3>" + _render_list(list(dict.fromkeys(gaps))))
    if opportunities:
        body_parts.append("<h3>Opportunities</h3>" + _render_list(opportunities))
    if not gaps and not opportunities:
        body_parts.append("<p><em>No research gaps identified.</em></p>")
    body_parts.append("</section>")

    body_parts.append("<section><h2>References</h2><ul>")
    by_id: Mapping[str, PaperAnalysis] = {p.paper_id: p for p in report.papers if p.paper_id}
    if report.citation_index:
        for paper_id, cite_key in sorted(report.citation_index.items(), key=lambda item: item[1]):
            paper = by_id.get(paper_id)
            title = paper.title if paper else paper_id
            body_parts.append(f"<li>[{_esc(cite_key)}] {_esc(title)}</li>")
    elif report.papers:
        for paper in report.papers:
            body_parts.append(f"<li>{_esc(paper.title)}</li>")
    else:
        body_parts.append("<li><em>No references available.</em></li>")
    body_parts.append("</ul></section>")

    if report.exports.get("bibtex"):
        body_parts.extend(
            [
                "<section><h2>BibTeX</h2>",
                f"<pre><code>{_esc(report.exports['bibtex'])}</code></pre>",
                "</section>",
            ]
        )

    body_parts.append("<section><h2>Appendix: All Papers</h2>")
    if report.papers:
        for index, paper in enumerate(report.papers, start=1):
            cite = ""
            if paper.paper_id and paper.paper_id in report.citation_index:
                cite = f" [{_esc(report.citation_index[paper.paper_id])}]"
            body_parts.append(f"<h3>{index}. {_esc(paper.title)}{cite}</h3>")
            meta = " | ".join(part for part in (str(paper.year) if paper.year else "", paper.venue or "") if part)
            if meta:
                body_parts.append(f"<p>{_esc(meta)}</p>")
            if paper.key_points:
                body_parts.append("<h4>Key points</h4>" + _render_list(list(paper.key_points)))
    else:
        body_parts.append("<p><em>No papers retrieved.</em></p>")
    body_parts.append("</section>")

    body = "\n".join(body_parts)
    print_css = _print_stylesheet() if pdf_ready else ""
    body_class = ' class="pdf-ready"' if pdf_ready else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(report.query)} — Research Report</title>
  <style>
    :root {{
      --text: #1a1a1a;
      --muted: #555;
      --accent: #2563eb;
      --border: #e5e7eb;
      --notice-bg: #fffbeb;
    }}
    body {{
      font-family: Georgia, "Times New Roman", serif;
      line-height: 1.6;
      color: var(--text);
      max-width: 820px;
      margin: 2rem auto;
      padding: 0 1.5rem 3rem;
    }}
    h1, h2, h3 {{ line-height: 1.25; }}
    h2 {{ border-bottom: 1px solid var(--border); padding-bottom: 0.25rem; margin-top: 2rem; }}
    section {{ margin-bottom: 1.5rem; }}
    .notice {{ background: var(--notice-bg); border: 1px solid #fcd34d; padding: 1rem; border-radius: 6px; }}
    pre {{
      background: #f8fafc;
      border: 1px solid var(--border);
      padding: 1rem;
      overflow-x: auto;
      font-size: 0.85rem;
    }}
    ul {{ padding-left: 1.25rem; }}
    @media print {{
      body {{ max-width: none; margin: 0; }}
      section {{ page-break-inside: avoid; }}
    }}
    {print_css}
  </style>
</head>
<body{body_class}>
{body}
</body>
</html>
"""


def render_pdf_ready_html(
    report: EnhancedResearchReport,
    *,
    partial: bool = False,
    warnings: list[str] | None = None,
) -> str:
    """Render HTML optimized for PDF export (print CSS, page margins, breaks)."""
    return render_html_report(
        report,
        partial=partial,
        warnings=warnings,
        pdf_ready=True,
    )


def _print_stylesheet() -> str:
    """Return additional CSS for PDF/print export."""
    return """
    @page {
      size: A4;
      margin: 2cm 2.2cm 2.4cm 2.2cm;
    }
    body.pdf-ready {
      max-width: none;
      margin: 0;
      padding: 0;
      font-size: 11pt;
      orphans: 3;
      widows: 3;
    }
    body.pdf-ready h1 {
      font-size: 20pt;
      margin-bottom: 0.75rem;
      page-break-after: avoid;
    }
    body.pdf-ready h2 {
      font-size: 14pt;
      margin-top: 1.5rem;
      page-break-after: avoid;
    }
    body.pdf-ready h3 {
      font-size: 12pt;
      page-break-after: avoid;
    }
    body.pdf-ready section {
      page-break-inside: avoid;
    }
    body.pdf-ready .notice {
      border-radius: 0;
      page-break-inside: avoid;
    }
    body.pdf-ready pre {
      white-space: pre-wrap;
      word-break: break-word;
      page-break-inside: avoid;
    }
    body.pdf-ready a {
      color: var(--text);
      text-decoration: none;
    }
    @media print {
      body.pdf-ready {
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }
      body.pdf-ready h2,
      body.pdf-ready h3 {
        break-after: avoid-page;
      }
      body.pdf-ready section {
        break-inside: avoid-page;
      }
    }
    """
