# -*- coding: utf-8 -*-
"""Retrieval provider abstraction."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import aiohttp
from pydantic import BaseModel, Field

from ...utils.logging_system import logger
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

    async def _request_with_retry(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 60,
        max_retries: int = 3,
        as_json: bool = True,
    ) -> object:
        """GET a URL with exponential backoff and Retry-After handling.

        Returns parsed JSON when ``as_json`` is true, otherwise the body text.
        """
        for attempt in range(max_retries):
            try:
                async with session.get(
                    url, params=params, headers=headers, timeout=timeout
                ) as response:
                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", "5"))
                        logger.warning(
                            "%s rate limited; retrying in %ss", self.name, retry_after
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    response.raise_for_status()
                    if as_json:
                        return await response.json(content_type=None)
                    return await response.text()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == max_retries - 1:
                    raise
                logger.warning(
                    "%s request failed (attempt %d): %s", self.name, attempt + 1, exc
                )
                await asyncio.sleep(2**attempt)
        raise aiohttp.ClientError(f"{self.name}: retries exhausted")
