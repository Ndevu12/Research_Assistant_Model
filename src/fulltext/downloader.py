# -*- coding: utf-8 -*-
"""PDF download stubs for future full-text ingestion."""

from __future__ import annotations

from .base import FullTextDocument, PDFDownloader


class StubPDFDownloader(PDFDownloader):
    """Placeholder downloader that documents the intended download flow."""

    async def download(self, paper_id: str, url: str) -> FullTextDocument:
        raise NotImplementedError(
            "PDF download is not yet implemented. "
            "Future versions will fetch open-access PDFs, cache them under "
            "data/fulltext/, and return a FullTextDocument with local_path set."
        )
