# -*- coding: utf-8 -*-
"""Canonical paper registry for ranking boosts and metadata checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..config.settings import _default_config_dir


@dataclass(frozen=True)
class CanonicalWork:
    title: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    doi_prefix: str | None = None


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def fuzzy_title_match(paper_title: str, canonical_title: str) -> bool:
    """Return True when paper title closely matches a canonical entry."""
    normalized_paper = _normalize_title(paper_title)
    normalized_canonical = _normalize_title(canonical_title)
    if not normalized_canonical:
        return False
    if normalized_paper == normalized_canonical:
        return True
    if normalized_canonical in normalized_paper or normalized_paper in normalized_canonical:
        return True

    paper_tokens = set(normalized_paper.split())
    canonical_tokens = set(normalized_canonical.split())
    if not canonical_tokens:
        return False
    overlap = len(paper_tokens & canonical_tokens) / len(canonical_tokens)
    return overlap >= 0.85


def match_canonical_work(paper_title: str, works: list[CanonicalWork]) -> CanonicalWork | None:
    """Return the first canonical work whose title fuzzy-matches the paper."""
    for work in works:
        if fuzzy_title_match(paper_title, work.title):
            return work
    return None


def _parse_works(raw: Any) -> list[CanonicalWork]:
    if not isinstance(raw, list):
        return []

    works: list[CanonicalWork] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        title = entry.get("title")
        if not title:
            continue
        authors_raw = entry.get("authors") or []
        authors = tuple(str(author) for author in authors_raw)
        year = entry.get("year")
        doi_prefix = entry.get("doi_prefix")
        works.append(
            CanonicalWork(
                title=str(title),
                authors=authors,
                year=int(year) if year is not None else None,
                doi_prefix=str(doi_prefix) if doi_prefix else None,
            )
        )
    return works


@lru_cache(maxsize=4)
def load_canonical_works(config_dir: str | None = None) -> list[CanonicalWork]:
    """Load canonical works from ``config/canonical_works.yaml``."""
    directory = Path(config_dir) if config_dir else _default_config_dir()
    path = directory / "canonical_works.yaml"
    if not path.is_file():
        return []

    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    return _parse_works(data.get("works"))
