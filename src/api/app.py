# -*- coding: utf-8 -*-
"""FastAPI application factory (optional dependency)."""

from __future__ import annotations

from typing import Any

from ..config.settings import AppSettings, get_settings
from ..core.registry import bootstrap_default_plugins, get_registry
from ..reporting.output import render_report_output
from ..retrieval.models import EnhancedResearchReport
from ..retrieval.orchestrator import build_pipeline


def create_app(settings: AppSettings | None = None) -> Any:
    """Create a FastAPI app exposing the research pipeline over HTTP."""
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise ImportError(
            "FastAPI is required for the API server. "
            "Install with: pipenv install fastapi uvicorn"
        ) from exc

    bootstrap_default_plugins()
    resolved_settings = settings or get_settings()
    registry = get_registry()

    class ResearchRequest(BaseModel):
        query: str = Field(min_length=1)
        format: str = Field(default="json", pattern="^(markdown|json|html)$")
        export: list[str] | None = None

    class HealthResponse(BaseModel):
        status: str
        providers: list[str]
        stages: list[str]

    app = FastAPI(
        title="Research Assistant API",
        description="Thin HTTP layer over the composable research pipeline.",
        version="0.1.0",
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            providers=registry.list_retrieval_providers(),
            stages=registry.list_stages(),
        )

    @app.get("/providers")
    async def list_providers() -> dict[str, list[str]]:
        return {"providers": registry.list_retrieval_providers()}

    @app.post("/research")
    async def run_research(request: ResearchRequest) -> dict[str, Any]:
        pipeline = build_pipeline(resolved_settings)
        try:
            result = await pipeline.execute(request.query)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        report = result.output
        if not isinstance(report, EnhancedResearchReport):
            artifact = result.artifacts.get("enhanced_report")
            if artifact:
                report = EnhancedResearchReport.model_validate(artifact)
            else:
                report = EnhancedResearchReport(query=request.query)

        rendered = render_report_output(
            report,
            output_format=request.format,
            partial=result.partial,
            warnings=result.warnings,
            export_formats=request.export,
        )

        return {
            "query": request.query,
            "format": request.format,
            "partial": result.partial,
            "warnings": result.warnings,
            "duration_ms": result.duration_ms,
            "session_id": result.session_id,
            "metrics": result.metrics,
            "report": report.model_dump(mode="json"),
            "rendered": rendered,
        }

    return app
