# -*- coding: utf-8 -*-
"""Shared helpers for citation export formats."""

from __future__ import annotations

import re

from ..retrieval.models import RetrievedPaper


def first_author_last_name(authors: list[str]) -> str:
    if not authors:
        return "Anonymous"
    parts = authors[0].split()
    return parts[-1] if parts else "Anonymous"


def format_author_list_apa(authors: list[str]) -> str:
    if not authors:
        return "Anonymous."
    formatted: list[str] = []
    for author in authors:
        parts = author.split()
        if len(parts) >= 2:
            initials = " ".join(f"{part[0]}." for part in parts[:-1])
            formatted.append(f"{parts[-1]}, {initials}")
        else:
            formatted.append(f"{author}.")
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]}, & {formatted[1]}"
    return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"


def format_author_list_mla(authors: list[str]) -> str:
    if not authors:
        return "Anonymous."
    if len(authors) == 1:
        parts = authors[0].split()
        if len(parts) >= 2:
            return f"{parts[-1]}, {' '.join(parts[:-1])}."
        return f"{authors[0]}."
    first = format_author_list_mla([authors[0]]).rstrip(".")
    return f"{first}, et al."


def format_author_list_chicago(authors: list[str]) -> str:
    if not authors:
        return "Anonymous"
    if len(authors) == 1:
        parts = authors[0].split()
        if len(parts) >= 2:
            return f"{parts[-1]}, {' '.join(parts[:-1])}"
        return authors[0]
    first = format_author_list_chicago([authors[0]])
    others = ", ".join(authors[1:])
    return f"{first}, and {others}"


def paper_access_url(paper: RetrievedPaper) -> str | None:
    return paper.doi or paper.url


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip())
