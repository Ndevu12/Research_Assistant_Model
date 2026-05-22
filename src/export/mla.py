# -*- coding: utf-8 -*-
"""MLA citation export (9th edition style)."""

from __future__ import annotations

from ..retrieval.models import RetrievedPaper
from ._common import format_author_list_mla, normalize_title, paper_access_url


def format_mla_entry(paper: RetrievedPaper) -> str:
    """Format a single MLA works-cited entry."""
    authors = format_author_list_mla(paper.authors)
    title = f'"{normalize_title(paper.title)}."'
    container = f" *{paper.venue}*," if paper.venue else ""
    year = f" {paper.year}," if paper.year else ""

    access = paper_access_url(paper)
    access_part = f" {access}." if access else ""

    return f"{authors} {title}{container}{year}{access_part}".strip().rstrip(",")


def generate_mla(papers: list[RetrievedPaper]) -> str:
    """Generate MLA works-cited list for papers."""
    if not papers:
        return ""
    return "\n\n".join(format_mla_entry(paper) for paper in papers)
