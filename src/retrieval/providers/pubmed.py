# -*- coding: utf-8 -*-
"""PubMed retrieval provider backed by NCBI E-utilities.

Searches with ``esearch`` (PMIDs, relevance-sorted) and hydrates metadata,
including abstracts, with ``efetch`` XML. An optional ``NCBI_API_KEY``
raises NCBI's rate limits but is not required.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

import aiohttp

from ..models import RetrievedPaper
from .base import RetrievalProvider

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedProvider(RetrievalProvider):
    """Retrieval provider for NCBI PubMed."""

    name = "pubmed"
    _search_url = f"{_EUTILS_BASE}/esearch.fcgi"
    _fetch_url = f"{_EUTILS_BASE}/efetch.fcgi"

    def _base_params(self) -> dict[str, str]:
        params = {"db": "pubmed"}
        api_key = os.getenv("NCBI_API_KEY")
        if api_key:
            params["api_key"] = api_key
        return params

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        resolved_limit = self.resolve_limit(limit)

        search_data = await self._request_with_retry(
            session,
            self._search_url,
            params={
                **self._base_params(),
                "term": query,
                "retmax": str(resolved_limit),
                "retmode": "json",
                "sort": "relevance",
            },
        )
        pmids = (search_data or {}).get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        body = await self._request_with_retry(
            session,
            self._fetch_url,
            params={
                **self._base_params(),
                "id": ",".join(pmids),
                "rettype": "abstract",
                "retmode": "xml",
            },
            as_json=False,
        )
        records = self._parse_efetch_xml(str(body))
        return [self.normalize(record) for record in records][:resolved_limit]

    def _parse_efetch_xml(self, body: str) -> list[dict]:
        """Convert efetch PubmedArticle XML into esummary-style dicts."""
        root = ET.fromstring(body)
        records: list[dict] = []

        for article in root.findall(".//PubmedArticle"):
            citation = article.find("MedlineCitation")
            if citation is None:
                continue
            article_node = citation.find("Article")
            if article_node is None:
                continue

            abstract_parts = [
                "".join(part.itertext()).strip()
                for part in article_node.findall(".//Abstract/AbstractText")
            ]
            doi = None
            for eloc in article_node.findall("ELocationID"):
                if eloc.get("EIdType") == "doi" and eloc.text:
                    doi = eloc.text.strip()
                    break
            if doi is None:
                for article_id in article.findall(".//ArticleIdList/ArticleId"):
                    if article_id.get("IdType") == "doi" and article_id.text:
                        doi = article_id.text.strip()
                        break

            authors = []
            for author in article_node.findall(".//AuthorList/Author"):
                last = author.findtext("LastName") or ""
                fore = author.findtext("ForeName") or ""
                full = f"{fore} {last}".strip()
                if full:
                    authors.append(full)

            title_node = article_node.find("ArticleTitle")
            # Explicit None check: ET elements without children are falsy.
            title = "".join(title_node.itertext()).strip() if title_node is not None else ""

            records.append(
                {
                    "pmid": citation.findtext("PMID"),
                    "title": title,
                    "abstract": "\n".join(part for part in abstract_parts if part) or None,
                    "pubdate": article_node.findtext(".//Journal/JournalIssue/PubDate/Year")
                    or citation.findtext(".//DateCompleted/Year"),
                    "source": article_node.findtext(".//Journal/Title"),
                    "doi": doi,
                    "authors": authors,
                    "keywords": [
                        keyword.text.strip()
                        for keyword in citation.findall(".//KeywordList/Keyword")
                        if keyword.text
                    ],
                }
            )

        return records

    async def _ping(self, session: aiohttp.ClientSession) -> bool:
        data = await self._request_with_retry(
            session,
            self._search_url,
            params={**self._base_params(), "term": "cancer", "retmax": "1", "retmode": "json"},
            timeout=15,
            max_retries=1,
        )
        return bool((data or {}).get("esearchresult"))

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
