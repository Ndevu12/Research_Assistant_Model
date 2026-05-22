# -*- coding: utf-8 -*-
"""Retrieval provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import aiohttp
from pydantic import BaseModel, Field

from ..models import RetrievedPaper

if TYPE_CHECKING:
    from ...config.settings import ProviderConfig


class ProviderHealth(BaseModel):
    """Health-check result for a retrieval provider."""

    provider: str
    healthy: bool
    latency_ms: float | None = None
    message: str = ""


class RetrievalProvider(ABC):
    """Interface for academic paper retrieval backends."""

    name: ClassVar[str]

    def __init__(self, config: ProviderConfig | None = None) -> None:
        from ...config.settings import ProviderConfig

        self.config = config or ProviderConfig()

    @abstractmethod
    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievedPaper]:
        """Search for papers matching the query."""

    @abstractmethod
    def normalize(self, raw: dict) -> RetrievedPaper:
        """Convert a provider-specific raw record into a RetrievedPaper."""

    async def health_check(self, session: aiohttp.ClientSession) -> ProviderHealth:
        """Check whether the provider API is reachable."""
        import time

        started = time.perf_counter()
        try:
            healthy = await self._ping(session)
            latency_ms = (time.perf_counter() - started) * 1000
            return ProviderHealth(
                provider=self.name,
                healthy=healthy,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            return ProviderHealth(
                provider=self.name,
                healthy=False,
                latency_ms=latency_ms,
                message=str(exc),
            )

    async def _ping(self, session: aiohttp.ClientSession) -> bool:
        """Perform a lightweight availability check."""
        return True

    def resolve_limit(self, limit: int | None) -> int:
        """Resolve the effective result limit for a search."""
        if limit is not None:
            return limit
        return self.config.limit
