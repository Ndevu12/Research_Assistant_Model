# -*- coding: utf-8 -*-
"""Pipeline observability metrics."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PipelineMetrics(BaseModel):
    """Aggregated metrics collected during pipeline execution."""

    stage_durations_ms: dict[str, float] = Field(default_factory=dict)
    retrieval_papers_found: int = 0
    retrieval_providers_failed: list[str] = Field(default_factory=list)
    ranking_top_score: float | None = None
    clustering_num_clusters: int | None = None
    llm_tokens_in: int = 0
    llm_tokens_out: int = 0
    llm_latency_ms: float = 0.0
    pipeline_total_duration_ms: float = 0.0
    degraded_stages: list[str] = Field(default_factory=list)
    custom: dict[str, Any] = Field(default_factory=dict)

    def record_stage(
        self,
        stage_name: str,
        duration_ms: float,
        partial: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.stage_durations_ms[stage_name] = duration_ms
        if partial:
            if stage_name not in self.degraded_stages:
                self.degraded_stages.append(stage_name)
        if extra:
            self.custom.setdefault("stages", {})[stage_name] = extra

    def record_retrieval(
        self,
        papers_found: int,
        providers_failed: list[str] | None = None,
    ) -> None:
        self.retrieval_papers_found = papers_found
        if providers_failed:
            self.retrieval_providers_failed.extend(providers_failed)

    def record_ranking(self, top_score: float) -> None:
        self.ranking_top_score = top_score

    def record_clustering(self, num_clusters: int) -> None:
        self.clustering_num_clusters = num_clusters

    def record_llm_usage(
        self,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
    ) -> None:
        self.llm_tokens_in += tokens_in
        self.llm_tokens_out += tokens_out
        self.llm_latency_ms += latency_ms

    def finalize(self, total_duration_ms: float) -> None:
        self.pipeline_total_duration_ms = total_duration_ms

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def emit_to_logger(self, logger: Any) -> None:
        """Emit structured metrics to the application logger."""
        logger.log_performance(
            "pipeline.total",
            duration_ms=self.pipeline_total_duration_ms,
            success=len(self.degraded_stages) == 0,
            extra_data={
                "retrieval.papers_found": self.retrieval_papers_found,
                "retrieval.providers_failed": self.retrieval_providers_failed,
                "ranking.top_score": self.ranking_top_score,
                "clustering.num_clusters": self.clustering_num_clusters,
                "llm.tokens_in": self.llm_tokens_in,
                "llm.tokens_out": self.llm_tokens_out,
                "llm.latency_ms": self.llm_latency_ms,
                "pipeline.degraded_stages": self.degraded_stages,
                "pipeline.stage_durations_ms": self.stage_durations_ms,
            },
        )

        if self.retrieval_papers_found or self.retrieval_providers_failed:
            logger.log_event(
                "pipeline.retrieval",
                f"Retrieved {self.retrieval_papers_found} papers",
                extra_data={
                    "papers_found": self.retrieval_papers_found,
                    "providers_failed": self.retrieval_providers_failed,
                },
            )

        if self.degraded_stages:
            logger.log_event(
                "pipeline.degraded",
                f"Pipeline completed with degraded stages: {', '.join(self.degraded_stages)}",
                level="warning",
                extra_data={"degraded_stages": self.degraded_stages},
            )
