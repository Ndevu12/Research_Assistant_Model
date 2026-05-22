# -*- coding: utf-8 -*-
"""Unified citation export across BibTeX, APA, MLA, and Chicago."""

from __future__ import annotations

from ..retrieval.models import RetrievedPaper
from .apa import generate_apa
from .bibtex import build_citation_index, generate_bibtex
from .chicago import generate_chicago
from .mla import generate_mla

SUPPORTED_FORMATS = frozenset({"bibtex", "apa", "mla", "chicago"})


def generate_citation_exports(
    papers: list[RetrievedPaper],
    formats: list[str] | None = None,
) -> dict[str, str]:
    """Generate citation exports for the requested formats."""
    requested = formats or list(SUPPORTED_FORMATS)
    exports: dict[str, str] = {}

    if "bibtex" in requested:
        exports["bibtex"] = generate_bibtex(papers)
    if "apa" in requested:
        exports["apa"] = generate_apa(papers)
    if "mla" in requested:
        exports["mla"] = generate_mla(papers)
    if "chicago" in requested:
        exports["chicago"] = generate_chicago(papers)

    citation_index = build_citation_index(papers)
    exports["citation_keys"] = "\n".join(
        f"{paper_id}: {key}" for paper_id, key in sorted(citation_index.items())
    )
    return exports
