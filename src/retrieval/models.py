# -*- coding: utf-8 -*-
"""Data models for the retrieval module."""

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field


@dataclass
class RetrievedPaper:
    """Represents a paper retrieved from a search source."""
    title: str
    abstract: Optional[str]
    year: Optional[int]
    venue: Optional[str]
    url: Optional[str]
    doi: Optional[str]
    source: str


class PaperAnalysis(BaseModel):
    """Analysis of a single paper."""
    title: str
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    key_points: list[str] = Field(default_factory=list)
    why_relevant: list[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    """Complete research report with query and paper analyses."""
    query: str
    papers: list[PaperAnalysis]
