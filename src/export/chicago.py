# -*- coding: utf-8 -*-
"""Chicago author-date citation export."""

from __future__ import annotations

from ..retrieval.models import RetrievedPaper
from ._common import format_author_list_chicago, normalize_title, paper_access_url


def format_chicago_entry(paper: RetrievedPaper) -> str:
    """Format a single Chicago author-date reference entry."""
    authors = format_author_list_chicago(paper.authors)
    year = str(paper.year) if paper.year else "n.d."
    title = f'"{normalize_title(paper.title)}."'
    venue = f" *{paper.venue}*." if paper.venue else ""

    access = paper_access_url(paper)
    if access:
        if access.startswith("10."):
            access_part = f" https://doi.org/{access}."
        else:
            access_part = f" {access}."
    else:
        access_part = ""

    return f"{authors}. {year}. {title}{venue}{access_part}".strip()


def generate_chicago(papers: list[RetrievedPaper]) -> str:
    """Generate Chicago reference list for papers."""
    if not papers:
        return ""
    return "\n\n".join(format_chicago_entry(paper) for paper in papers)
