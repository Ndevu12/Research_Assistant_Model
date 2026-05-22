# -*- coding: utf-8 -*-
"""Shared base for Phase 3 retrieval provider stubs."""

from __future__ import annotations

from typing import ClassVar

import aiohttp

from .base import ProviderHealth, RetrievalProvider


class StubRetrievalProvider(RetrievalProvider):
    """Base class for providers that are registered but not yet implemented."""

    _stub_message: ClassVar[str] = "Provider not yet implemented."

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list:
        raise NotImplementedError(self._stub_message)

    async def health_check(self, session: aiohttp.ClientSession) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            healthy=False,
            latency_ms=0.0,
            message=self._stub_message,
        )
