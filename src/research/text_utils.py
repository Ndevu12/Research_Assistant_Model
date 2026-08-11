# -*- coding: utf-8 -*-
"""Shared text heuristics used across ranking, filtering, and clustering."""

from __future__ import annotations

import re

QUERY_STOP_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "paper",
        "papers",
        "research",
        "study",
        "studies",
    }
)

LABEL_STOP_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "using",
        "based",
        "via",
        "from",
    }
)

GENERIC_QUERY_TERMS = frozenset(
    {
        "mechanism",
        "mechanisms",
        "method",
        "methods",
        "approach",
        "approaches",
        "application",
        "applications",
        "model",
        "models",
        "system",
        "systems",
        "based",
        "using",
        "recent",
    }
)


def extract_query_terms(query: str) -> set[str]:
    """Return meaningful lowercase terms from a query."""
    words = re.findall(r"\b\w+\b", query.lower())
    return {word for word in words if word not in QUERY_STOP_WORDS and len(word) > 2}


def extract_core_concepts(query: str) -> list[str]:
    """Extract core concept terms from a query."""
    words = re.findall(r"\b\w+\b", query.lower())
    return [word for word in words if word not in QUERY_STOP_WORDS and len(word) > 3][:5]


def term_matches_text(term: str, text: str) -> bool:
    """Return True when a term (or its simple plural/singular form) occurs in text."""
    if term in text:
        return True
    if term.endswith("s") and term[:-1] in text:
        return True
    return f"{term}s" in text
