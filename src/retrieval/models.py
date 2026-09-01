# -*- coding: utf-8 -*-
"""Data models for the retrieval and research pipeline."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class RetrievedPaper(BaseModel):
    """Paper retrieved from a search provider."""

    model_config = ConfigDict(populate_by_name=True)

    title: str
    abstract: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    provider: str = Field(validation_alias=AliasChoices("provider", "source"))
    citation_count: Optional[int] = None
    authors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    embedding_id: Optional[str] = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def source(self) -> str:
        """Backward-compatible alias for :attr:`provider`."""
        return self.provider

    @property
    def paper_id(self) -> str:
        """Stable identifier for clustering and cross-references."""
        if self.doi:
            return self.doi
        if self.url:
            return self.url
        return self.title


class PaperAnalysis(BaseModel):
    """Analysis of a single paper."""

    paper_id: Optional[str] = None
    title: str
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    key_points: list[str] = Field(default_factory=list)
    why_relevant: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    """Complete research report with query and paper analyses."""

    query: str
    papers: list[PaperAnalysis]


class QueryUnderstandingResult(BaseModel):
    """Structured output from query understanding."""

    intent: str = ""
    constraints: dict[str, Any] = Field(default_factory=dict)
    key_concepts: list[str] = Field(default_factory=list)


class ExpandedQuerySet(BaseModel):
    """Original query plus generated variants and sub-questions."""

    original: str
    variants: list[str] = Field(default_factory=list)
    sub_questions: list[str] = Field(default_factory=list)


class RankedPaper(BaseModel):
    """Retrieved paper with ranking score and signal breakdown."""

    paper: RetrievedPaper
    rank_score: float = 0.0
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class PaperCluster(BaseModel):
    """Thematic grouping of related papers."""

    theme: str
    summary: str = ""
    paper_ids: list[str] = Field(default_factory=list)


class PaperExtraction(BaseModel):
    """Structured per-paper extraction from Pass A of synthesis."""

    paper_id: str
    title: str
    methodology: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    benchmarks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class SynthesisResult(BaseModel):
    """Cross-paper synthesis from collective analysis."""

    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    trends: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    methodologies: list[str] = Field(default_factory=list)


class GapAnalysisResult(BaseModel):
    """Prioritized research gaps and opportunities."""

    gaps: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    underexplored_areas: list[str] = Field(default_factory=list)


class EnhancedResearchReport(BaseModel):
    """Extended research report with synthesis, clusters, and exports."""

    query: str
    executive_summary: str = ""
    papers: list[PaperAnalysis] = Field(default_factory=list)
    clusters: list[PaperCluster] = Field(default_factory=list)
    synthesis: Optional[SynthesisResult] = None
    gap_analysis: Optional[GapAnalysisResult] = None
    gaps: list[str] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)
    citation_index: dict[str, str] = Field(default_factory=dict)
    exports: dict[str, str] = Field(default_factory=dict)

    def to_research_report(self) -> ResearchReport:
        """Convert to the legacy report shape used by existing renderers."""
        return ResearchReport(query=self.query, papers=self.papers)
