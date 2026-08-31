# -*- coding: utf-8 -*-
"""Golden evaluation dataset models and loader."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ..retrieval.models import RetrievedPaper

DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parent.parent.parent / "evals" / "golden_set.yaml"
)


class GoldenCandidate(BaseModel):
    """One candidate paper with a graded relevance label.

    ``relevance``: 0 = irrelevant, 1 = relevant, 2 = highly relevant.
    """

    title: str
    relevance: int = Field(ge=0, le=2)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    abstract: str | None = None
    citation_count: int | None = None
    provider: str = "golden"

    def to_paper(self) -> RetrievedPaper:
        return RetrievedPaper(
            title=self.title,
            year=self.year,
            venue=self.venue,
            doi=self.doi,
            abstract=self.abstract,
            citation_count=self.citation_count,
            provider=self.provider,
        )


class GoldenQuery(BaseModel):
    """A query with labeled candidates."""

    query: str
    domain: str = "general"
    candidates: list[GoldenCandidate]

    @property
    def relevant_titles(self) -> set[str]:
        return {c.title for c in self.candidates if c.relevance >= 1}

    @property
    def relevance_by_title(self) -> dict[str, int]:
        return {c.title: c.relevance for c in self.candidates}


class GoldenDataset(BaseModel):
    """The full golden evaluation set."""

    version: int = 1
    queries: list[GoldenQuery]


def load_golden_dataset(path: Path | None = None) -> GoldenDataset:
    """Load the golden dataset from YAML."""
    resolved = path or DEFAULT_DATASET_PATH
    with resolved.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return GoldenDataset.model_validate(payload)
