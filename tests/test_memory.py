# -*- coding: utf-8 -*-
"""Tests for SQLite memory store and session cache."""

from __future__ import annotations

import pytest
import pytest_asyncio

from src.config.settings import AppSettings, MemoryConfig
from src.core.context import ResearchSession
from src.memory.store import MemoryStore, build_cache_key, build_config_hash
from src.retrieval.models import RetrievedPaper


@pytest_asyncio.fixture
async def memory_store(tmp_path) -> MemoryStore:
    store = MemoryStore(MemoryConfig(db_path=str(tmp_path / "test.db")))
    await store.initialize()
    return store


@pytest.mark.asyncio
async def test_create_and_load_session(memory_store: MemoryStore) -> None:
    session = ResearchSession(last_query="transformers")
    created = await memory_store.create_session(session)
    loaded = await memory_store.load_session(created.id)

    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.last_query == "transformers"


@pytest.mark.asyncio
async def test_save_search_papers_and_report(memory_store: MemoryStore) -> None:
    session = await memory_store.create_session()
    search_id = await memory_store.save_search(
        session.id,
        "machine learning",
        expanded_queries=["deep learning", "ML"],
        cache_key="abc123",
    )
    papers = [
        RetrievedPaper(title="Paper A", year=2023, provider="openalex", doi="10.1/a"),
        RetrievedPaper(title="Paper B", year=2024, provider="semantic_scholar"),
    ]
    await memory_store.save_papers(search_id, papers)
    report_id = await memory_store.save_report(session.id, "markdown", "# Report")

    assert search_id == 1
    assert report_id == 1

    cached = await memory_store.get_cached_search("abc123")
    assert cached is not None
    assert len(cached.papers) == 2
    assert cached.query == "machine learning"

    reports = await memory_store.list_reports(session.id)
    assert len(reports) == 1
    assert reports[0].format == "markdown"


@pytest.mark.asyncio
async def test_cache_key_is_stable() -> None:
    settings = AppSettings()
    config_hash = build_config_hash(settings)
    key_a = build_cache_key("Transformers NLP", ["openalex"], config_hash)
    key_b = build_cache_key("transformers nlp", ["openalex"], config_hash)
    assert key_a == key_b


@pytest.mark.asyncio
async def test_update_session_context(memory_store: MemoryStore) -> None:
    session = await memory_store.create_session()
    session.context_json = {"last_report": {"query": "test"}}
    await memory_store.update_session(session)

    loaded = await memory_store.load_session(session.id)
    assert loaded is not None
    assert loaded.context_json["last_report"]["query"] == "test"
