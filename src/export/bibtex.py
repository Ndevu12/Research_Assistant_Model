# -*- coding: utf-8 -*-
"""BibTeX citation export."""

from __future__ import annotations

import re

from ..retrieval.models import RetrievedPaper


def _first_author_key(authors: list[str]) -> str:
    if not authors:
        return "anon"
    parts = authors[0].split()
    return re.sub(r"[^a-z]", "", parts[-1].lower()) if parts else "anon"


def _title_token(title: str) -> str:
    words = re.findall(r"\b[a-z0-9]+\b", title.lower())
    return words[0] if words else "paper"


def make_citation_key(paper: RetrievedPaper) -> str:
    """Build a stable BibTeX citation key from paper metadata."""
    author = _first_author_key(paper.authors)
    year = str(paper.year) if paper.year else "nd"
    token = _title_token(paper.title)
    return f"{author}{year}{token}"


def _escape_bibtex(value: str) -> str:
    return value.replace("{", "\\{").replace("}", "\\}")


def format_bibtex_entry(paper: RetrievedPaper, key: str | None = None) -> str:
    """Format a single BibTeX entry for a paper."""
    cite_key = key or make_citation_key(paper)
    fields: list[str] = [f"  title = {{{_escape_bibtex(paper.title)}}}"]

    if paper.authors:
        author_str = " and ".join(paper.authors)
        fields.append(f"  author = {{{_escape_bibtex(author_str)}}}")
    if paper.year:
        fields.append(f"  year = {{{paper.year}}}")
    if paper.venue:
        fields.append(f"  journal = {{{_escape_bibtex(paper.venue)}}}")
    if paper.doi:
        fields.append(f"  doi = {{{paper.doi}}}")
    elif paper.url:
        fields.append(f"  url = {{{paper.url}}}")

    body = ",\n".join(fields)
    return f"@article{{{cite_key},\n{body}\n}}"


def build_citation_index(papers: list[RetrievedPaper]) -> dict[str, str]:
    """Map paper IDs to citation keys."""
    keys_used: dict[str, int] = {}
    index: dict[str, str] = {}

    for paper in papers:
        base_key = make_citation_key(paper)
        count = keys_used.get(base_key, 0)
        keys_used[base_key] = count + 1
        key = base_key if count == 0 else f"{base_key}{count}"
        index[paper.paper_id] = key

    return index


def generate_bibtex(papers: list[RetrievedPaper]) -> str:
    """Generate BibTeX entries for a list of papers."""
    if not papers:
        return ""

    index = build_citation_index(papers)
    id_to_key = {paper.paper_id: index[paper.paper_id] for paper in papers}
    entries = [format_bibtex_entry(paper, key=id_to_key[paper.paper_id]) for paper in papers]
    return "\n\n".join(entries)
