# -*- coding: utf-8 -*-
"""Tests for full-text grounding: resolver, parser, chunker, index, stage."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.settings import AppSettings
from src.core.context import PipelineContext
from src.fulltext.base import FullTextChunk, FullTextDocument
from src.fulltext.chunker import SectionAwareChunker
from src.fulltext.rag import InMemoryFulltextIndex
from src.fulltext.resolver import resolve_pdf_url
from src.fulltext.stage import PASSAGES_ARTIFACT, FulltextStage
from src.retrieval.models import RankedPaper, RetrievedPaper


def _paper(title: str = "Paper", **overrides) -> RetrievedPaper:
    defaults = {"title": title, "provider": "test"}
    defaults.update(overrides)
    return RetrievedPaper(**defaults)


def _ranked(paper: RetrievedPaper, score: float = 0.8) -> RankedPaper:
    return RankedPaper(paper=paper, rank_score=score, score_breakdown={})


class TestResolver:
    def test_arxiv_url_from_abs_link(self) -> None:
        paper = _paper(url="https://arxiv.org/abs/1706.03762v5")
        assert resolve_pdf_url(paper) == "https://arxiv.org/pdf/1706.03762"

    def test_arxiv_url_from_datacite_doi(self) -> None:
        paper = _paper(doi="https://doi.org/10.48550/arXiv.2205.14135")
        assert resolve_pdf_url(paper) == "https://arxiv.org/pdf/2205.14135"

    def test_openalex_best_oa_location(self) -> None:
        paper = _paper(
            raw_metadata={
                "best_oa_location": {"pdf_url": "https://repo.org/paper.pdf", "is_oa": True}
            }
        )
        assert resolve_pdf_url(paper) == "https://repo.org/paper.pdf"

    def test_openalex_oa_url_fallback(self) -> None:
        paper = _paper(raw_metadata={"open_access": {"oa_url": "https://oa.org/x.pdf"}})
        assert resolve_pdf_url(paper) == "https://oa.org/x.pdf"

    def test_core_download_url(self) -> None:
        paper = _paper(raw_metadata={"downloadUrl": "https://core.ac.uk/download/9.pdf"})
        assert resolve_pdf_url(paper) == "https://core.ac.uk/download/9.pdf"

    def test_closed_access_resolves_to_none(self) -> None:
        assert resolve_pdf_url(_paper(url="https://publisher.example/paywall")) is None


class TestParser:
    def test_extracts_sections_and_truncates_references(self, tmp_path: Path) -> None:
        pymupdf = pytest.importorskip("pymupdf")

        pdf_path = tmp_path / "sample.pdf"
        document = pymupdf.open()
        page = document.new_page()
        body = (
            "A Study of Testing\n"
            "Abstract\n"
            "This paper studies automated testing of research pipelines in depth.\n"
            "1 Introduction\n"
            "Testing pipelines end to end catches integration regressions early.\n"
            "References\n"
            "[1] Some Citation That Should Not Appear.\n"
        )
        page.insert_text((72, 72), body)
        document.save(pdf_path)
        document.close()

        from src.fulltext.parser import extract_document

        parsed = extract_document("paper-1", pdf_path)

        assert parsed.page_count == 1
        assert parsed.text is not None
        assert "studies automated testing" in parsed.text
        assert "## Abstract" in parsed.text
        assert "## Introduction" in parsed.text
        assert "Some Citation" not in parsed.text
        assert parsed.metadata["sections"]["abstract"] == 1


class TestChunker:
    def test_section_markers_tag_chunks(self) -> None:
        text = (
            "## Abstract\n\n"
            + "Sentence about attention mechanisms. " * 10
            + "\n\n## Methods\n\n"
            + "Details of the experimental setup and datasets. " * 10
        )
        document = FullTextDocument(paper_id="p1", text=text)

        chunks = SectionAwareChunker(max_chars=600, overlap_chars=50).chunk(document)

        assert chunks
        sections = {chunk.metadata["section"] for chunk in chunks}
        assert {"abstract", "methods"} <= sections
        assert all(chunk.paper_id == "p1" for chunk in chunks)

    def test_long_text_is_split_with_overlap(self) -> None:
        text = "\n\n".join(f"Paragraph {i} " + "content words here. " * 20 for i in range(6))
        document = FullTextDocument(paper_id="p1", text=text)

        chunks = SectionAwareChunker(max_chars=800, overlap_chars=100).chunk(document)

        assert len(chunks) >= 2
        assert all(len(chunk.text) >= 200 for chunk in chunks)

    def test_empty_document_yields_no_chunks(self) -> None:
        assert SectionAwareChunker().chunk(FullTextDocument(paper_id="p1")) == []


class TestFulltextIndex:
    async def test_bm25_fallback_search_scoped_to_paper(self) -> None:
        index = InMemoryFulltextIndex(embedder=None)
        await index.index_chunks(
            [
                FullTextChunk(
                    paper_id="p1",
                    chunk_index=0,
                    text="Scaled dot-product attention drives the transformer architecture.",
                ),
                FullTextChunk(
                    paper_id="p1",
                    chunk_index=1,
                    text="The optimizer used warmup steps during training.",
                ),
                FullTextChunk(
                    paper_id="p2",
                    chunk_index=0,
                    text="Attention in convolutional models differs entirely.",
                ),
            ]
        )

        results = await index.search("transformer attention", top_k=1, paper_id="p1")

        assert len(results) == 1
        assert results[0].paper_id == "p1"
        assert "transformer" in results[0].text

    async def test_empty_index_returns_nothing(self) -> None:
        index = InMemoryFulltextIndex(embedder=None)
        assert await index.search("anything") == []


class FakeDownloader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.calls: list[str] = []

    async def download(self, paper_id: str, url: str, session=None) -> FullTextDocument:
        self.calls.append(url)
        return FullTextDocument(paper_id=paper_id, source_url=url, local_path=self.path)


class TestFulltextStage:
    async def test_passthrough_when_disabled(self) -> None:
        settings = AppSettings(fulltext={"enabled": False})
        ctx = PipelineContext.create("query", settings)
        ranked = [_ranked(_paper())]

        result = await FulltextStage().run(ctx, ranked)

        assert result.output == ranked
        assert result.metrics["papers_with_passages"] == 0

    async def test_passthrough_when_no_open_access_urls(self) -> None:
        settings = AppSettings(fulltext={"enabled": True})
        ctx = PipelineContext.create("query", settings)
        ranked = [_ranked(_paper(url="https://publisher.example/paywalled"))]

        result = await FulltextStage().run(ctx, ranked)

        assert result.output == ranked
        assert result.metrics.get("pdfs_resolved") == 0

    async def test_stage_produces_passages_artifact(self, tmp_path: Path) -> None:
        pytest.importorskip("pymupdf")
        from unittest.mock import patch

        settings = AppSettings(fulltext={"enabled": True, "top_chunks_per_paper": 2})
        ctx = PipelineContext.create("transformer attention", settings)
        paper = _paper(
            "Attention Paper",
            url="https://arxiv.org/abs/1706.03762",
            abstract="Attention mechanisms.",
        )
        ranked = [_ranked(paper)]

        parsed = FullTextDocument(
            paper_id=paper.paper_id,
            text=(
                "## Abstract\n\n"
                "Scaled dot-product attention is the core of the transformer model "
                "and enables parallel sequence processing at scale for translation. "
                "It replaces recurrence entirely across encoder and decoder stacks, "
                "and multi-head attention lets the model attend to information from "
                "different representation subspaces jointly."
            ),
            metadata={"sections": {"abstract": 1}},
        )

        with patch(
            "src.fulltext.parser.extract_document", return_value=parsed
        ) as mock_extract:
            stage = FulltextStage(
                downloader=FakeDownloader(tmp_path / "cached.pdf"),
                index=InMemoryFulltextIndex(embedder=None),
            )
            result = await stage.run(ctx, ranked)

        assert mock_extract.called
        assert result.metrics["papers_with_passages"] == 1
        passages = ctx.get_artifact(PASSAGES_ARTIFACT)
        assert paper.paper_id in passages
        assert "dot-product attention" in passages[paper.paper_id][0]

    async def test_download_failure_degrades_gracefully(self) -> None:
        settings = AppSettings(fulltext={"enabled": True})
        ctx = PipelineContext.create("query", settings)
        ranked = [_ranked(_paper(url="https://arxiv.org/abs/1706.03762"))]

        class FailingDownloader:
            async def download(self, paper_id, url, session=None):
                raise RuntimeError("download failed")

        result = await FulltextStage(downloader=FailingDownloader()).run(ctx, ranked)

        assert result.output == ranked
        assert result.metrics["papers_with_passages"] == 0


class TestEvidenceInSynthesis:
    def test_heuristic_extraction_includes_evidence_from_passages(self) -> None:
        from src.analysis.synthesis import _heuristic_extraction

        ranked = _ranked(_paper("Grounded Paper", abstract="First point. Second point."))
        passages = ["A verbatim passage from the paper full text " * 12]

        extraction = _heuristic_extraction(ranked, passages)

        assert extraction.evidence
        assert extraction.evidence[0].endswith("…")
        assert len(extraction.evidence[0]) <= 301
        assert "full-text passages" in extraction.methodology[0]

    def test_extraction_prompt_embeds_passages(self) -> None:
        from src.analysis.synthesis import _build_extraction_prompt

        ranked = _ranked(_paper("Grounded Paper", abstract="Abstract text."))
        prompt = _build_extraction_prompt(
            ranked, "test query", ["Passage one text.", "Passage two text."]
        )

        assert "[Passage 1] Passage one text." in prompt
        assert "[Passage 2] Passage two text." in prompt
        assert "verbatim" in prompt

    def test_markdown_renders_evidence_quotes(self) -> None:
        from src.reporting.markdown import render_enhanced_markdown
        from src.retrieval.models import EnhancedResearchReport, PaperAnalysis, PaperCluster

        report = EnhancedResearchReport(
            query="q",
            papers=[
                PaperAnalysis(
                    paper_id="p1",
                    title="Grounded Paper",
                    key_points=["Finding one"],
                    evidence=["Attention replaces recurrence entirely."],
                )
            ],
            clusters=[PaperCluster(theme="Theme", summary="", paper_ids=["p1"])],
        )

        rendered = render_enhanced_markdown(report)

        assert "Evidence (from full text):" in rendered
        assert "> Attention replaces recurrence entirely." in rendered
