# -*- coding: utf-8 -*-
"""Tests for the PubMed, DBLP, and CORE retrieval providers."""

from __future__ import annotations

from unittest.mock import patch

import aiohttp
import pytest

from src.retrieval.providers.core_provider import CoreProvider
from src.retrieval.providers.dblp import DblpProvider
from src.retrieval.providers.pubmed import PubMedProvider

_PUBMED_EFETCH_XML = """<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <Journal>
          <JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue>
          <Title>Nature Medicine</Title>
        </Journal>
        <ArticleTitle>CRISPR base editing in vivo</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Base editing enables precise changes.</AbstractText>
          <AbstractText Label="RESULTS">Efficient editing was observed.</AbstractText>
        </Abstract>
        <ELocationID EIdType="doi">10.1038/example-doi</ELocationID>
        <AuthorList>
          <Author><LastName>Doe</LastName><ForeName>Jane</ForeName></Author>
          <Author><LastName>Smith</LastName><ForeName>John</ForeName></Author>
        </AuthorList>
      </Article>
      <KeywordList><Keyword>gene editing</Keyword></KeywordList>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


class TestPubMedProvider:
    async def test_search_chains_esearch_and_efetch(self) -> None:
        provider = PubMedProvider()
        calls: list[str] = []

        async def fake_request(session, url, *, params=None, as_json=True, **kwargs):
            calls.append(url)
            if "esearch" in url:
                assert params["term"] == "crispr base editing"
                return {"esearchresult": {"idlist": ["12345678"]}}
            assert params["id"] == "12345678"
            return _PUBMED_EFETCH_XML

        with patch.object(PubMedProvider, "_request_with_retry", side_effect=fake_request):
            async with aiohttp.ClientSession() as session:
                papers = await provider.search(session, "crispr base editing", limit=5)

        assert len(calls) == 2
        assert len(papers) == 1
        paper = papers[0]
        assert paper.title == "CRISPR base editing in vivo"
        assert paper.year == 2020
        assert paper.venue == "Nature Medicine"
        assert paper.doi == "https://doi.org/10.1038/example-doi"
        assert paper.url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
        assert "Base editing enables precise changes." in paper.abstract
        assert paper.authors == ["Jane Doe", "John Smith"]
        assert paper.keywords == ["gene editing"]
        assert paper.provider == "pubmed"

    async def test_search_returns_empty_when_no_ids(self) -> None:
        provider = PubMedProvider()

        async def fake_request(session, url, **kwargs):
            return {"esearchresult": {"idlist": []}}

        with patch.object(PubMedProvider, "_request_with_retry", side_effect=fake_request):
            async with aiohttp.ClientSession() as session:
                papers = await provider.search(session, "nonexistent topic")

        assert papers == []


class TestDblpProvider:
    async def test_search_normalizes_hits(self) -> None:
        provider = DblpProvider()
        payload = {
            "result": {
                "hits": {
                    "hit": [
                        {
                            "info": {
                                "title": "Attention Is All You Need.",
                                "venue": "NIPS",
                                "year": "2017",
                                "doi": "10.5555/EXAMPLE",
                                "ee": "https://example.org/paper",
                                "authors": {
                                    "author": [
                                        {"text": "Ashish Vaswani"},
                                        {"text": "Noam Shazeer"},
                                    ]
                                },
                            }
                        }
                    ]
                }
            }
        }

        async def fake_request(session, url, *, params=None, **kwargs):
            assert params["format"] == "json"
            return payload

        with patch.object(DblpProvider, "_request_with_retry", side_effect=fake_request):
            async with aiohttp.ClientSession() as session:
                papers = await provider.search(session, "attention", limit=3)

        assert len(papers) == 1
        paper = papers[0]
        assert paper.title == "Attention Is All You Need"
        assert paper.year == 2017
        assert paper.venue == "NIPS"
        assert paper.doi == "https://doi.org/10.5555/EXAMPLE"
        assert paper.url == "https://example.org/paper"
        assert paper.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert paper.provider == "dblp"

    async def test_search_handles_empty_results(self) -> None:
        provider = DblpProvider()

        async def fake_request(session, url, **kwargs):
            return {"result": {"hits": {}}}

        with patch.object(DblpProvider, "_request_with_retry", side_effect=fake_request):
            async with aiohttp.ClientSession() as session:
                papers = await provider.search(session, "obscure")

        assert papers == []


class TestCoreProvider:
    async def test_search_requires_api_key(self, monkeypatch) -> None:
        monkeypatch.delenv("CORE_API_KEY", raising=False)
        provider = CoreProvider()

        async with aiohttp.ClientSession() as session:
            with pytest.raises(RuntimeError, match="CORE_API_KEY"):
                await provider.search(session, "open access")

    async def test_health_check_reports_missing_key(self, monkeypatch) -> None:
        monkeypatch.delenv("CORE_API_KEY", raising=False)
        provider = CoreProvider()

        async with aiohttp.ClientSession() as session:
            health = await provider.health_check(session)

        assert health.healthy is False
        assert "CORE_API_KEY" in health.message

    async def test_search_normalizes_results(self, monkeypatch) -> None:
        monkeypatch.setenv("CORE_API_KEY", "test-key")
        provider = CoreProvider()
        payload = {
            "results": [
                {
                    "title": "Open Access Study",
                    "abstract": "A study of open access publishing.",
                    "publishedDate": "2021-04-01",
                    "doi": "10.1234/oa-study",
                    "downloadUrl": "https://core.ac.uk/download/1.pdf",
                    "publisher": "Example Press",
                    "authors": [{"name": "Ada Lovelace"}],
                    "citationCount": 42,
                }
            ]
        }

        async def fake_request(session, url, *, headers=None, **kwargs):
            assert headers["Authorization"] == "Bearer test-key"
            return payload

        with patch.object(CoreProvider, "_request_with_retry", side_effect=fake_request):
            async with aiohttp.ClientSession() as session:
                papers = await provider.search(session, "open access", limit=5)

        assert len(papers) == 1
        paper = papers[0]
        assert paper.title == "Open Access Study"
        assert paper.year == 2021
        assert paper.doi == "https://doi.org/10.1234/oa-study"
        assert paper.url == "https://core.ac.uk/download/1.pdf"
        assert paper.venue == "Example Press"
        assert paper.authors == ["Ada Lovelace"]
        assert paper.citation_count == 42
        assert paper.provider == "core"
