# -*- coding: utf-8 -*-
"""Async SQLite persistence for research sessions and cache."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from ..config.settings import AppSettings, MemoryConfig
from ..core.context import ResearchSession
from ..retrieval.models import RetrievedPaper
from .schemas import CacheLookupResult, StoredReport, StoredSearch, StoredSession

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_query TEXT,
    context_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    query TEXT NOT NULL,
    expanded_queries TEXT NOT NULL DEFAULT '[]',
    cache_key TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_searches_cache_key ON searches(cache_key);

CREATE TABLE IF NOT EXISTS papers (
    search_id INTEGER NOT NULL,
    paper_json TEXT NOT NULL,
    embedding_blob BLOB,
    FOREIGN KEY (search_id) REFERENCES searches(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    format TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _dt_to_str(value: datetime) -> str:
    return value.isoformat()


def _str_to_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def build_cache_key(
    query: str,
    provider_names: list[str],
    config_hash: str,
) -> str:
    """Build a stable cache key from query, providers, and config."""
    normalized_query = " ".join(query.lower().split())
    provider_part = ",".join(sorted(provider_names))
    payload = f"{normalized_query}|{provider_part}|{config_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_config_hash(settings: AppSettings) -> str:
    """Hash retrieval-relevant settings for cache invalidation."""
    payload = {
        "providers": {
            name: cfg.model_dump()
            for name, cfg in settings.retrieval.providers.items()
        },
        "per_provider_limit": settings.retrieval.per_provider_limit,
        "ranking_top_k": settings.ranking.top_k,
    }
    encoded = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


class MemoryStore:
    """SQLite-backed store for sessions, searches, papers, and reports."""

    def __init__(self, config: MemoryConfig) -> None:
        self.config = config
        self._db_path = Path(config.db_path)

    @property
    def db_path(self) -> Path:
        return self._db_path

    async def initialize(self) -> None:
        """Create database file and schema if needed."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()

    async def create_session(self, session: ResearchSession | None = None) -> ResearchSession:
        """Persist a new research session."""
        resolved = session or ResearchSession()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO sessions (id, created_at, last_query, context_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    resolved.id,
                    _dt_to_str(resolved.created_at),
                    resolved.last_query,
                    json.dumps(resolved.context_json),
                ),
            )
            await db.commit()
        return resolved

    async def update_session(self, session: ResearchSession) -> None:
        """Update session metadata and context."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                UPDATE sessions
                SET last_query = ?, context_json = ?
                WHERE id = ?
                """,
                (
                    session.last_query,
                    json.dumps(session.context_json),
                    session.id,
                ),
            )
            await db.commit()

    async def load_session(self, session_id: str) -> StoredSession | None:
        """Load a session by ID."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, created_at, last_query, context_json FROM sessions WHERE id = ?",
                (session_id,),
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return None
        return StoredSession(
            id=row["id"],
            created_at=_str_to_dt(row["created_at"]),
            last_query=row["last_query"],
            context_json=json.loads(row["context_json"] or "{}"),
        )

    async def save_search(
        self,
        session_id: str,
        query: str,
        expanded_queries: list[str] | None = None,
        cache_key: str | None = None,
    ) -> int:
        """Record a search and return its database ID."""
        now = _utc_now()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO searches (session_id, query, expanded_queries, cache_key, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    query,
                    json.dumps(expanded_queries or []),
                    cache_key,
                    _dt_to_str(now),
                ),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def save_papers(self, search_id: int, papers: list[RetrievedPaper]) -> None:
        """Persist retrieved papers for a search."""
        async with aiosqlite.connect(self._db_path) as db:
            for paper in papers:
                await db.execute(
                    """
                    INSERT INTO papers (search_id, paper_json, embedding_blob)
                    VALUES (?, ?, ?)
                    """,
                    (search_id, paper.model_dump_json(), None),
                )
            await db.commit()

    async def save_report(self, session_id: str, fmt: str, content: str) -> int:
        """Persist a rendered report."""
        now = _utc_now()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO reports (session_id, format, content, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, fmt, content, _dt_to_str(now)),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def get_cached_search(self, cache_key: str) -> CacheLookupResult | None:
        """Return cached papers for a cache key, if any."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, session_id, query, expanded_queries
                FROM searches
                WHERE cache_key = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (cache_key,),
            ) as cursor:
                search_row = await cursor.fetchone()
            if search_row is None:
                return None

            search_id = int(search_row["id"])
            async with db.execute(
                "SELECT paper_json FROM papers WHERE search_id = ?",
                (search_id,),
            ) as cursor:
                paper_rows = await cursor.fetchall()

        papers = [json.loads(row["paper_json"]) for row in paper_rows]
        if not papers:
            return None

        return CacheLookupResult(
            search_id=search_id,
            session_id=search_row["session_id"],
            query=search_row["query"],
            expanded_queries=json.loads(search_row["expanded_queries"] or "[]"),
            papers=papers,
        )

    async def list_reports(self, session_id: str) -> list[StoredReport]:
        """List reports saved for a session."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, session_id, format, content, timestamp
                FROM reports
                WHERE session_id = ?
                ORDER BY id DESC
                """,
                (session_id,),
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            StoredReport(
                id=row["id"],
                session_id=row["session_id"],
                format=row["format"],
                content=row["content"],
                timestamp=_str_to_dt(row["timestamp"]),
            )
            for row in rows
        ]

    def session_from_stored(self, stored: StoredSession) -> ResearchSession:
        """Convert a stored session row to a runtime session model."""
        return ResearchSession(
            id=stored.id,
            created_at=stored.created_at,
            last_query=stored.last_query,
            context_json=dict(stored.context_json),
        )

    async def close(self) -> None:
        """No-op placeholder for API symmetry."""
