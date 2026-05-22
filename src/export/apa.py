# -*- coding: utf-8 -*-
"""APA citation export (7th edition style)."""

from __future__ import annotations

from ..retrieval.models import RetrievedPaper
from ._common import format_author_list_apa, normalize_title, paper_access_url


def format_apa_entry(paper: RetrievedPaper) -> str:
    """Format a single APA reference entry."""
    authors = format_author_list_apa(paper.authors)
    year = f"({paper.year})." if paper.year else "(n.d.)."
    title = normalize_title(paper.title)
    title_part = f"*{title}*."
    venue_part = f" *{paper.venue}*." if paper.venue else ""

    access = paper_access_url(paper)
    if access:
        if access.startswith("10."):
            doi_part = f" https://doi.org/{access}"
        else:
            doi_part = f" {access}"
    else:
        doi_part = ""

    return f"{authors} {year} {title_part}{venue_part}{doi_part}".strip()


def generate_apa(papers: list[RetrievedPaper]) -> str:
    """Generate APA reference list for papers."""
    if not papers:
        return ""
    return "\n\n".join(format_apa_entry(paper) for paper in papers)
