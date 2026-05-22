# -*- coding: utf-8 -*-
"""PubMed retrieval provider (Phase 3 stub).

Future flow: NCBI E-utilities ``esearch`` + ``esummary``/``efetch`` with API key
rate limits, MeSH-aware query expansion, and PMID/PMCID normalization.
"""

from __future__ import annotations

import re
from typing import ClassVar

from ..models import RetrievedPaper
from ._stub_base import StubRetrievalProvider


class PubMedProvider(StubRetrievalProvider):
    """Retrieval provider stub for NCBI PubMed."""

    name = "pubmed"
    _stub_message: ClassVar[str] = (
        "PubMed provider is not yet implemented. "
        "Future versions will query NCBI E-utilities (esearch/esummary)."
    )

    def normalize(self, raw: dict) -> RetrievedPaper:
        """Convert an NCBI esummary-style record into a RetrievedPaper."""
        title = raw.get("title") or raw.get("Title") or "Untitled"
        abstract = raw.get("abstract") or raw.get("Abstract") or None

        year = raw.get("year") or raw.get("pubdate")
        if isinstance(year, str):
            match = re.search(r"(\d{4})", year)
            year = int(match.group(1)) if match else None
        elif year is not None:
            year = int(year)

        doi = raw.get("doi") or raw.get("elocationid")
        if doi and not str(doi).startswith("http"):
            doi = f"https://doi.org/{doi}"

        pmid = raw.get("pmid") or raw.get("uid") or raw.get("Id")
        url = raw.get("url")
        if not url and pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        authors = raw.get("authors") or []
        if not authors and raw.get("AuthorList"):
            authors = [
                f"{author.get('LastName', '')} {author.get('ForeName', '')}".strip()
                for author in raw["AuthorList"]
                if isinstance(author, dict)
            ]

        return RetrievedPaper(
            title=str(title),
            abstract=abstract,
            year=year,
            venue=raw.get("source") or raw.get("Source") or raw.get("journal"),
            url=url,
            doi=doi or None,
            provider=self.name,
            authors=[name for name in authors if name],
            keywords=list(raw.get("keywords") or raw.get("Keywords") or []),
            raw_metadata=raw,
        )
