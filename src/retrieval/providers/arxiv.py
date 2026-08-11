# -*- coding: utf-8 -*-
"""arXiv retrieval provider."""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET

import aiohttp

from ..models import RetrievedPaper
from ...utils.logging_system import logger
from ...utils.message_formatter import MessageFormatter
from .base import RetrievalProvider

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"
_NAMESPACES = {"atom": _ATOM_NS, "arxiv": _ARXIV_NS}


class ArxivProvider(RetrievalProvider):
    """Retrieval provider backed by the arXiv Atom API."""

    name = "arxiv"
    _search_url = "https://export.arxiv.org/api/query"

    def _search_query(self, query: str) -> str:
        cleaned = query.strip()
        if not cleaned:
            return "all:test"
        if ":" in cleaned.split()[0]:
            return cleaned
        return f"all:{cleaned}"

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        max_results = self.resolve_limit(limit)
        params = {
            "search_query": self._search_query(query),
            "start": "0",
            "max_results": str(max_results),
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with session.get(
                    self._search_url,
                    params=params,
                    timeout=60,
                ) as response:
                    response.raise_for_status()
                    body = await response.text()
                    break
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == max_retries - 1:
                    raise
                logger.warning(MessageFormatter.api_retry_message("arXiv", attempt + 1, str(exc)))
                await asyncio.sleep(2 ** attempt)
        else:
            logger.warning(MessageFormatter.api_max_retries_message("arXiv"))
            return []

        root = ET.fromstring(body)
        entries = root.findall("atom:entry", _NAMESPACES)
        return [self.normalize(self._entry_to_dict(entry)) for entry in entries]

    def _entry_to_dict(self, entry: ET.Element) -> dict:
        title = self._element_text(entry, "atom:title")
        summary = self._element_text(entry, "atom:summary")
        published = self._element_text(entry, "atom:published")
        entry_id = self._element_text(entry, "atom:id")

        authors = [
            self._element_text(author, "atom:name")
            for author in entry.findall("atom:author", _NAMESPACES)
        ]
        authors = [name for name in authors if name]

        pdf_url = None
        for link in entry.findall("atom:link", _NAMESPACES):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href")
                break

        primary_category = entry.find("arxiv:primary_category", _NAMESPACES)
        category = primary_category.attrib.get("term") if primary_category is not None else None

        doi = self._element_text(entry, "arxiv:doi")
        journal_ref = self._element_text(entry, "arxiv:journal_ref")

        return {
            "id": entry_id,
            "title": title,
            "summary": summary,
            "published": published,
            "authors": authors,
            "pdf_url": pdf_url,
            "primary_category": category,
            "doi": doi,
            "journal_ref": journal_ref,
        }

    @staticmethod
    def _element_text(parent: ET.Element, tag: str) -> str:
        element = parent.find(tag, _NAMESPACES)
        if element is None or element.text is None:
            return ""
        return re.sub(r"\s+", " ", element.text).strip()

    def normalize(self, raw: dict) -> RetrievedPaper:
        year = None
        published = raw.get("published") or ""
        if published:
            match = re.match(r"(\d{4})", published)
            if match:
                year = int(match.group(1))

        doi = raw.get("doi")
        if doi and not str(doi).startswith("http"):
            doi = f"https://doi.org/{doi}"

        venue = raw.get("journal_ref") or raw.get("primary_category")
        url = raw.get("id") or raw.get("pdf_url")

        return RetrievedPaper(
            title=raw.get("title") or "Untitled",
            abstract=raw.get("summary") or None,
            year=year,
            venue=venue,
            url=url,
            doi=doi or None,
            provider=self.name,
            authors=list(raw.get("authors") or []),
            raw_metadata=raw,
        )

    async def _ping(self, session: aiohttp.ClientSession) -> bool:
        async with session.get(
            self._search_url,
            params={"search_query": "all:test", "max_results": "1"},
            timeout=15,
        ) as response:
            response.raise_for_status()
            return True
