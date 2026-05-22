# -*- coding: utf-8 -*-
"""Pydantic schemas for persisted research memory records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StoredSession(BaseModel):
    """Row from the sessions table."""

    id: str
    created_at: datetime
    last_query: str | None = None
    context_json: dict[str, Any] = Field(default_factory=dict)


class StoredSearch(BaseModel):
    """Row from the searches table."""

    id: int
    session_id: str
    query: str
    expanded_queries: list[str] = Field(default_factory=list)
    cache_key: str | None = None
    timestamp: datetime


class StoredPaper(BaseModel):
    """Paper payload linked to a search."""

    search_id: int
    paper_json: dict[str, Any]
    embedding_blob: bytes | None = None


class StoredReport(BaseModel):
    """Persisted report output."""

    id: int
    session_id: str
    format: str
    content: str
    timestamp: datetime


class CacheLookupResult(BaseModel):
    """Cached search result used to skip retrieval."""

    search_id: int
    session_id: str
    query: str
    expanded_queries: list[str] = Field(default_factory=list)
    papers: list[dict[str, Any]] = Field(default_factory=list)
