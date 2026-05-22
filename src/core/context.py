# -*- coding: utf-8 -*-
"""Pipeline execution context and stage result types."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from ..config.settings import AppSettings
from .metrics import PipelineMetrics

TOut = TypeVar("TOut")


class ResearchSession(BaseModel):
    """In-memory research session state (Phase 1 interface; persistence in Phase 2)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_query: str | None = None
    context_json: dict[str, Any] = Field(default_factory=dict)


class StageResult(BaseModel, Generic[TOut]):
    """Output of a single pipeline stage."""

    output: Any
    duration_ms: float
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    partial: bool = False


class PipelineContext:
    """Shared state passed through pipeline stages."""

    def __init__(
        self,
        query: str,
        config: AppSettings,
        session: ResearchSession | None = None,
    ) -> None:
        self.query = query
        self.config = config
        self.session = session or ResearchSession(last_query=query)
        self.session.last_query = query
        self.metrics = PipelineMetrics()
        self.warnings: list[str] = []
        self.stage_results: dict[str, StageResult[Any]] = {}
        self._artifacts: dict[str, Any] = {}

    @classmethod
    def create(
        cls,
        query: str,
        config: AppSettings,
        session: ResearchSession | None = None,
    ) -> PipelineContext:
        return cls(query=query, config=config, session=session)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def record_stage_result(self, stage_name: str, result: StageResult[Any]) -> None:
        self.stage_results[stage_name] = result
        self.warnings.extend(result.warnings)
        self.metrics.record_stage(
            stage_name,
            duration_ms=result.duration_ms,
            partial=result.partial,
            extra=result.metrics,
        )

    def set_artifact(self, key: str, value: Any) -> None:
        self._artifacts[key] = value

    def get_artifact(self, key: str, default: Any = None) -> Any:
        return self._artifacts.get(key, default)

    @property
    def is_partial(self) -> bool:
        return any(result.partial for result in self.stage_results.values())

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "session_id": self.session.id,
            "warnings": list(self.warnings),
            "partial": self.is_partial,
            "stage_results": {
                name: {
                    "duration_ms": result.duration_ms,
                    "partial": result.partial,
                    "warnings": result.warnings,
                    "metrics": result.metrics,
                }
                for name, result in self.stage_results.items()
            },
            "metrics": self.metrics.to_dict(),
            "artifacts": list(self._artifacts.keys()),
        }
