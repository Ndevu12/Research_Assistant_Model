# -*- coding: utf-8 -*-
"""Open-access PDF download with an on-disk cache."""

from __future__ import annotations

import hashlib
from pathlib import Path

import aiohttp

from ..utils.logging_system import logger
from .base import FullTextDocument, PDFDownloader


class CachingPDFDownloader(PDFDownloader):
    """Downloads PDFs once and caches them under a local directory."""

    def __init__(
        self,
        cache_dir: str = "data/fulltext",
        *,
        max_bytes: int = 15 * 1024 * 1024,
        timeout_seconds: int = 30,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.max_bytes = max_bytes
        self.timeout_seconds = timeout_seconds

    def _cache_path(self, paper_id: str) -> Path:
        digest = hashlib.sha256(paper_id.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}.pdf"

    async def download(
        self,
        paper_id: str,
        url: str,
        session: aiohttp.ClientSession | None = None,
    ) -> FullTextDocument:
        """Download a PDF (or reuse the cached copy) and return its metadata."""
        path = self._cache_path(paper_id)
        if path.is_file() and path.stat().st_size > 0:
            return FullTextDocument(paper_id=paper_id, source_url=url, local_path=path)

        if session is None:
            async with aiohttp.ClientSession() as owned_session:
                return await self.download(paper_id, url, session=owned_session)

        async with session.get(
            url,
            timeout=self.timeout_seconds,
            allow_redirects=True,
            headers={"User-Agent": "ResearchAssistant/1.0 (fulltext)"},
        ) as response:
            response.raise_for_status()
            content_type = (response.content_type or "").lower()
            body = await response.content.read(self.max_bytes + 1)

        if len(body) > self.max_bytes:
            raise ValueError(f"PDF exceeds size limit ({self.max_bytes} bytes): {url}")
        if not body.startswith(b"%PDF") and "pdf" not in content_type:
            raise ValueError(f"URL did not return a PDF (content-type {content_type}): {url}")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        logger.info("Cached full text for %s (%d KB)", paper_id, len(body) // 1024)
        return FullTextDocument(paper_id=paper_id, source_url=url, local_path=path)
