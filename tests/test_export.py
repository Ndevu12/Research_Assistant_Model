# -*- coding: utf-8 -*-
"""Tests for citation export formats."""

from __future__ import annotations

from src.export import generate_citation_exports
from src.export.apa import format_apa_entry, generate_apa
from src.export.bibtex import generate_bibtex, make_citation_key
from src.export.chicago import generate_chicago
from src.export.mla import generate_mla
from src.retrieval.models import RetrievedPaper


def _sample_paper() -> RetrievedPaper:
    return RetrievedPaper(
        title="Attention Is All You Need",
        year=2017,
        authors=["Ashish Vaswani", "Noam Shazeer"],
        venue="NeurIPS",
        doi="10.5555/3295222.3295349",
        provider="openalex",
    )


class TestBibTeXExport:
    def test_make_citation_key(self) -> None:
        assert make_citation_key(_sample_paper()) == "vaswani2017attention"

    def test_generate_bibtex_includes_metadata(self) -> None:
        bibtex = generate_bibtex([_sample_paper()])
        assert "@article{" in bibtex
        assert "Attention Is All You Need" in bibtex
        assert "Vaswani" in bibtex
        assert "2017" in bibtex


class TestAPAExport:
    def test_format_apa_entry(self) -> None:
        entry = format_apa_entry(_sample_paper())
        assert "Vaswani" in entry
        assert "(2017)" in entry
        assert "Attention Is All You Need" in entry
        assert "NeurIPS" in entry

    def test_generate_apa_multiple(self) -> None:
        paper_b = RetrievedPaper(title="BERT", year=2019, authors=["Jacob Devlin"], provider="openalex")
        result = generate_apa([_sample_paper(), paper_b])
        assert "Attention Is All You Need" in result
        assert "BERT" in result


class TestMLAExport:
    def test_generate_mla(self) -> None:
        mla = generate_mla([_sample_paper()])
        assert '"Attention Is All You Need."' in mla
        assert "Vaswani" in mla


class TestChicagoExport:
    def test_generate_chicago(self) -> None:
        chicago = generate_chicago([_sample_paper()])
        assert "2017" in chicago
        assert "Attention Is All You Need" in chicago


class TestUnifiedExport:
    def test_generate_all_formats(self) -> None:
        exports = generate_citation_exports([_sample_paper()])
        assert exports["bibtex"]
        assert exports["apa"]
        assert exports["mla"]
        assert exports["chicago"]
        assert "vaswani2017attention" in exports["citation_keys"]

    def test_selective_formats(self) -> None:
        exports = generate_citation_exports([_sample_paper()], formats=["apa", "mla"])
        assert "bibtex" not in exports
        assert exports["apa"]
        assert exports["mla"]
