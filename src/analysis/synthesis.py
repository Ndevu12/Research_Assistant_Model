# -*- coding: utf-8 -*-
"""Two-pass cross-paper synthesis workflow."""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

from pydantic_ai import Agent

from ..core.context import PipelineContext, StageResult
from ..core.paper_adapters import ensure_ranked_papers
from ..models import AgentFactory, AgentRole, create_llm_agent
from ..research.text_utils import extract_core_concepts
from ..retrieval.models import (
    PaperAnalysis,
    PaperCluster,
    PaperExtraction,
    RankedPaper,
    SynthesisResult,
)
from ..utils.enhanced_response_handler import EnhancedResponseHandler
from ..utils.logging_system import logger
from ..utils.response_models import RequestContext, ResponseHandlerConfig, RetryConfig

if TYPE_CHECKING:
    from ..config.settings import LLMConfig, SynthesisConfig


__all__ = ["create_llm_agent", "SynthesisStage", "extract_papers", "synthesize_collective"]

HEURISTIC_DISAGREEMENT_PLACEHOLDER = (
    "Cross-paper disagreement analysis limited in heuristic mode."
)

_CONFLICT_TERM_GROUPS = (
    ("outperform", "underperform"),
    ("better", "worse"),
    ("superior", "inferior"),
    ("increase", "decrease"),
    ("effective", "ineffective"),
)


def embedding_similarity_for_paper(paper: RankedPaper) -> float:
    """Return cached embedding similarity from ranking, if present."""
    return float(paper.score_breakdown.get("embedding_similarity", 0.0))


def sentence_aligns_with_query(sentence: str, concepts: list[str]) -> bool:
    """Return True when a sentence overlaps with at least one query concept."""
    if not concepts:
        return True
    lower = sentence.lower()
    return any(concept.lower() in lower for concept in concepts)


def _top_quartile_paper_ids(ranked_papers: list[RankedPaper]) -> set[str]:
    if not ranked_papers:
        return set()
    sorted_papers = sorted(
        ranked_papers,
        key=embedding_similarity_for_paper,
        reverse=True,
    )
    quartile_count = max(1, (len(sorted_papers) + 3) // 4)
    return {paper.paper.paper_id for paper in sorted_papers[:quartile_count]}


def _select_query_aligned_agreements(
    query: str,
    extractions: list[PaperExtraction],
    ranked_papers: list[RankedPaper] | None,
) -> list[str]:
    concepts = extract_core_concepts(query)
    top_ids = _top_quartile_paper_ids(ranked_papers or [])

    aligned_findings: list[str] = []
    for extraction in extractions:
        if top_ids and extraction.paper_id not in top_ids:
            continue
        for finding in extraction.findings:
            if sentence_aligns_with_query(finding, concepts):
                aligned_findings.append(finding)

    return list(dict.fromkeys(aligned_findings))[:3]


def _detect_conflicting_findings(extractions: list[PaperExtraction]) -> list[str]:
    conflicts: list[str] = []
    all_findings = [finding.lower() for extraction in extractions for finding in extraction.findings]

    for positive, negative in _CONFLICT_TERM_GROUPS:
        has_positive = any(positive in finding for finding in all_findings)
        has_negative = any(negative in finding for finding in all_findings)
        if has_positive and has_negative:
            conflicts.append(
                f"Papers report mixed evidence on whether approaches "
                f"{positive} or {negative} baselines."
            )

    methodologies = {
        item.lower()
        for extraction in extractions
        for item in extraction.methodology
        if item
    }
    if len(methodologies) >= 3:
        sample = sorted(methodologies)[:3]
        conflicts.append(f"Diverse methodological approaches: {', '.join(sample)}.")

    return list(dict.fromkeys(conflicts))[:3]


def _evidence_from_passages(passages: list[str] | None, limit: int = 2) -> list[str]:
    """Trim grounded passages into short verbatim evidence quotes."""
    if not passages:
        return []
    quotes: list[str] = []
    for passage in passages[:limit]:
        cleaned = " ".join(passage.split())
        quotes.append(cleaned[:300] + ("…" if len(cleaned) > 300 else ""))
    return quotes


def _heuristic_extraction(
    paper: RankedPaper,
    passages: list[str] | None = None,
) -> PaperExtraction:
    """Build a fallback extraction when the LLM pass is unavailable."""
    abstract = paper.paper.abstract or ""
    sentences = [part.strip() for part in abstract.split(".") if part.strip()]
    findings = sentences[:2] if sentences else [f"Discusses {paper.paper.title}."]
    limitations = sentences[2:3] if len(sentences) > 2 else []

    keywords = paper.paper.keywords or []
    datasets = [kw for kw in keywords if any(token in kw.lower() for token in ("data", "corpus", "benchmark"))]
    if not datasets and abstract:
        datasets = ["Not explicitly stated in abstract"]

    source_note = (
        ["Details inferred from abstract and full-text passages"]
        if passages
        else ["Details inferred from abstract only"]
    )

    return PaperExtraction(
        paper_id=paper.paper.paper_id,
        title=paper.paper.title,
        methodology=source_note,
        datasets=datasets,
        benchmarks=[],
        limitations=limitations,
        findings=findings,
        evidence=_evidence_from_passages(passages),
    )


def _heuristic_synthesis(
    query: str,
    extractions: list[PaperExtraction],
    clusters: list[PaperCluster],
    ranked_papers: list[RankedPaper] | None = None,
) -> SynthesisResult:
    """Aggregate extractions heuristically when collective synthesis fails."""
    all_datasets: list[str] = []
    all_methodologies: list[str] = []
    all_limitations: list[str] = []

    for extraction in extractions:
        all_datasets.extend(extraction.datasets)
        all_methodologies.extend(extraction.methodology)
        all_limitations.extend(extraction.limitations)

    unique_datasets = list(dict.fromkeys(item for item in all_datasets if item))
    unique_methodologies = list(dict.fromkeys(item for item in all_methodologies if item))

    cluster_themes = [cluster.theme for cluster in clusters if cluster.theme]
    trends = [
        f"Research grouped into {len(clusters)} thematic cluster(s): {', '.join(cluster_themes[:3])}."
    ] if clusters else [f"Literature review for: {query}"]

    gaps = list(dict.fromkeys(all_limitations))[:5]
    if not gaps:
        gaps = [f"Limited cross-paper comparison for query: {query}"]

    agreements = _select_query_aligned_agreements(query, extractions, ranked_papers)
    if len(agreements) < 2 and unique_methodologies:
        agreements = [f"Shared methodological themes: {', '.join(unique_methodologies[:3])}"]

    disagreements = _detect_conflicting_findings(extractions)
    if not disagreements:
        disagreements = [HEURISTIC_DISAGREEMENT_PLACEHOLDER]

    return SynthesisResult(
        agreements=agreements,
        disagreements=disagreements,
        trends=trends,
        gaps=gaps,
        datasets=unique_datasets[:10],
        methodologies=unique_methodologies[:10],
    )


def _build_extraction_prompt(
    paper: RankedPaper,
    query: str,
    passages: list[str] | None = None,
) -> str:
    abstract = paper.paper.abstract or "No abstract available."
    prompt = (
        f"Research query: {query}\n\n"
        f"Paper ID: {paper.paper.paper_id}\n"
        f"Title: {paper.paper.title}\n"
        f"Year: {paper.paper.year or 'unknown'}\n"
        f"Venue: {paper.paper.venue or 'unknown'}\n"
        f"Abstract: {abstract[:1200]}\n"
    )
    if passages:
        numbered = "\n\n".join(
            f"[Passage {index}] {passage[:1500]}"
            for index, passage in enumerate(passages, start=1)
        )
        prompt += (
            f"\nFull-text passages retrieved for this query:\n{numbered}\n\n"
            "Ground the extraction in these passages and quote short verbatim "
            "evidence snippets from them."
        )
    else:
        prompt += "\nExtract methodology, datasets, benchmarks, limitations, and findings."
    return prompt


def _build_synthesis_prompt(
    query: str,
    extractions: list[PaperExtraction],
    clusters: list[PaperCluster],
    ranked_papers: list[RankedPaper] | None = None,
) -> str:
    cluster_payload = [
        {"theme": cluster.theme, "summary": cluster.summary, "paper_ids": cluster.paper_ids}
        for cluster in clusters
    ]
    extraction_payload = [extraction.model_dump() for extraction in extractions]
    paper_years = {
        paper.paper.paper_id: paper.paper.year
        for paper in (ranked_papers or [])
        if paper.paper.year is not None
    }
    years = sorted(set(paper_years.values()))

    return (
        f"Research query: {query}\n\n"
        f"Thematic clusters:\n{json.dumps(cluster_payload, ensure_ascii=False)}\n\n"
        f"Structured paper extractions:\n{json.dumps(extraction_payload, ensure_ascii=False)}\n\n"
        f"Publication years present: {years}\n\n"
        "Synthesize agreements, disagreements, trends, gaps, datasets, and methodologies "
        "across all papers. Include benchmark comparisons where evident."
    )


def _extractions_to_paper_analyses(
    extractions: list[PaperExtraction],
    ranked_papers: list[RankedPaper] | None = None,
) -> list[PaperAnalysis]:
    metadata_by_id = {
        paper.paper.paper_id: paper.paper for paper in (ranked_papers or [])
    }
    analyses: list[PaperAnalysis] = []
    for extraction in extractions:
        source = metadata_by_id.get(extraction.paper_id)
        analyses.append(
            PaperAnalysis(
                paper_id=extraction.paper_id,
                title=extraction.title,
                year=source.year if source else None,
                venue=source.venue if source else None,
                url=source.url if source else None,
                doi=source.doi if source else None,
                key_points=extraction.findings,
                why_relevant=extraction.methodology,
                evidence=extraction.evidence,
            )
        )
    return analyses


def _synthesis_handler_config(max_retries: int) -> ResponseHandlerConfig:
    return ResponseHandlerConfig(
        retry_config=RetryConfig(max_retries=max_retries),
    )


def resolve_synthesis_input(data: object, ctx: PipelineContext) -> SynthesisResult:
    """Resolve a synthesis result from stage output or pipeline artifacts."""
    artifact = ctx.get_artifact("synthesis_result")
    if isinstance(artifact, SynthesisResult):
        return artifact
    if isinstance(data, SynthesisResult):
        return data
    return SynthesisResult()


def recover_synthesis_output(
    ctx: PipelineContext,
    clusters: list[PaperCluster],
) -> SynthesisResult:
    """Build heuristic synthesis when the synthesis stage times out or fails."""
    existing = ctx.get_artifact("synthesis_result")
    if isinstance(existing, SynthesisResult):
        return existing

    ranked_papers: list[RankedPaper] = ctx.get_artifact("ranked_papers") or []
    if not ranked_papers:
        retrieved = ctx.get_artifact("retrieved_papers") or []
        if retrieved:
            ranked_papers, _ = ensure_ranked_papers(
                retrieved,
                ctx.query,
                config=ctx.config.ranking,
            )

    resolved_clusters = clusters or ctx.get_artifact("paper_clusters") or []
    recovery_passages: dict[str, list[str]] = ctx.get_artifact("fulltext_passages") or {}
    extractions = [
        _heuristic_extraction(paper, recovery_passages.get(paper.paper.paper_id))
        for paper in ranked_papers
    ]
    synthesis = _heuristic_synthesis(
        ctx.query,
        extractions,
        resolved_clusters,
        ranked_papers=ranked_papers,
    )
    paper_analyses = _extractions_to_paper_analyses(extractions, ranked_papers)

    ctx.set_artifact("paper_extractions", extractions)
    ctx.set_artifact("paper_analyses", paper_analyses)
    ctx.set_artifact("synthesis_result", synthesis)
    ctx.set_artifact("ranked_papers", ranked_papers)
    return synthesis


async def _extract_single_paper(
    paper: RankedPaper,
    query: str,
    agent: Agent,
    handler: EnhancedResponseHandler,
    context: RequestContext,
    passages: list[str] | None = None,
) -> tuple[PaperExtraction, bool]:
    prompt = _build_extraction_prompt(paper, query, passages)
    result = await handler.process_structured_response(
        agent,
        prompt,
        context,
        PaperExtraction,
        schema_description=(
            '{"paper_id": "...", "title": "...", "methodology": ["..."], '
            '"datasets": ["..."], "benchmarks": ["..."], '
            '"limitations": ["..."], "findings": ["..."], "evidence": ["..."]}'
        ),
    )
    if result.success and isinstance(result.data, PaperExtraction):
        extraction = result.data
        if not extraction.evidence and passages:
            extraction = extraction.model_copy(
                update={"evidence": _evidence_from_passages(passages)}
            )
        return extraction, True
    return _heuristic_extraction(paper, passages), False


async def extract_papers(
    ranked_papers: list[RankedPaper],
    query: str,
    *,
    llm_config: LLMConfig | None = None,
    handler: EnhancedResponseHandler | None = None,
    concurrency: int = 4,
    session_id: str = "",
    synthesis_config: SynthesisConfig | None = None,
    passages: dict[str, list[str]] | None = None,
) -> list[PaperExtraction]:
    """Pass A — structured extraction for each ranked paper.

    ``passages`` maps paper IDs to query-relevant full-text passages from the
    fulltext stage; when present they ground both LLM and heuristic paths.
    """
    if not ranked_papers:
        return []
    passages = passages or {}

    if synthesis_config is None:
        from ..config.settings import get_settings

        synthesis_config = get_settings().synthesis

    if not synthesis_config.llm_enabled:
        logger.info(
            "Using heuristic paper extraction for %d paper(s) (synthesis.llm_enabled=false)",
            len(ranked_papers),
        )
        return [
            _heuristic_extraction(paper, passages.get(paper.paper.paper_id))
            for paper in ranked_papers
        ]

    max_llm_papers = max(1, synthesis_config.max_llm_papers)
    llm_targets = ranked_papers[:max_llm_papers]
    heuristic_targets = ranked_papers[max_llm_papers:]

    agent = AgentFactory(llm_config).create_agent(AgentRole.EXTRACTION, config=llm_config)
    response_handler = handler or EnhancedResponseHandler(
        _synthesis_handler_config(synthesis_config.extraction_max_retries)
    )
    context = RequestContext(
        user_query=query,
        model_name=llm_config.model if llm_config else "default",
        session_id=session_id,
    )

    from ..utils.progress_reporter import get_progress_reporter

    semaphore = asyncio.Semaphore(max(concurrency, 1))
    breaker = {"consecutive_failures": 0, "open": False}

    async def _extract_with_circuit(index: int, paper: RankedPaper) -> PaperExtraction:
        async with semaphore:
            paper_passages = passages.get(paper.paper.paper_id)
            if breaker["open"]:
                return _heuristic_extraction(paper, paper_passages)

            title_preview = paper.paper.title[:72]
            logger.info(
                "LLM extracting paper %d/%d: %s",
                index,
                len(llm_targets),
                paper.paper.title[:80],
            )

            reporter = get_progress_reporter()
            if reporter is not None:
                reporter.set_activity(
                    f"Analyzing paper {index}/{len(llm_targets)}: {title_preview}…"
                )

            extraction, llm_success = await _extract_single_paper(
                paper,
                query,
                agent,
                response_handler,
                context,
                passages=paper_passages,
            )

        if llm_success:
            breaker["consecutive_failures"] = 0
        else:
            breaker["consecutive_failures"] += 1
            if (
                not breaker["open"]
                and breaker["consecutive_failures"]
                >= synthesis_config.circuit_breaker_failures
            ):
                breaker["open"] = True
                logger.warning(
                    "LLM extraction circuit breaker open after %d failures; "
                    "using heuristics for remaining papers",
                    breaker["consecutive_failures"],
                )

        return extraction

    llm_extractions = list(
        await asyncio.gather(
            *(
                _extract_with_circuit(index, paper)
                for index, paper in enumerate(llm_targets, start=1)
            )
        )
    )

    heuristic_extractions = [
        _heuristic_extraction(paper, passages.get(paper.paper.paper_id))
        for paper in heuristic_targets
    ]
    return llm_extractions + heuristic_extractions


async def synthesize_collective(
    query: str,
    extractions: list[PaperExtraction],
    clusters: list[PaperCluster],
    *,
    ranked_papers: list[RankedPaper] | None = None,
    llm_config: LLMConfig | None = None,
    handler: EnhancedResponseHandler | None = None,
    session_id: str = "",
    synthesis_config: SynthesisConfig | None = None,
) -> SynthesisResult:
    """Pass B — collective cross-paper synthesis."""
    if not extractions:
        return SynthesisResult()

    if synthesis_config is None:
        from ..config.settings import get_settings

        synthesis_config = get_settings().synthesis

    if not synthesis_config.llm_enabled:
        logger.info("Using heuristic collective synthesis (synthesis.llm_enabled=false)")
        return _heuristic_synthesis(query, extractions, clusters, ranked_papers=ranked_papers)

    if llm_config is None:
        from ..config.settings import get_settings

        llm_config = get_settings().llm

    agent = AgentFactory(llm_config).create_agent(AgentRole.SYNTHESIS, config=llm_config)
    response_handler = handler or EnhancedResponseHandler(
        _synthesis_handler_config(synthesis_config.collective_max_retries)
    )
    context = RequestContext(
        user_query=query,
        model_name=llm_config.model,
        session_id=session_id,
    )
    prompt = _build_synthesis_prompt(query, extractions, clusters, ranked_papers)

    logger.info("Running LLM collective synthesis across %d paper(s)", len(extractions))
    from ..utils.progress_reporter import get_progress_reporter

    reporter = get_progress_reporter()
    if reporter is not None:
        reporter.set_activity(
            f"Synthesizing insights across {len(extractions)} paper(s)…"
        )

    result = await response_handler.process_structured_response(
        agent,
        prompt,
        context,
        SynthesisResult,
        schema_description=(
            '{"agreements": ["..."], "disagreements": ["..."], "trends": ["..."], '
            '"gaps": ["..."], "datasets": ["..."], "methodologies": ["..."]}'
        ),
    )
    if result.success and isinstance(result.data, SynthesisResult):
        return result.data
    logger.warning("LLM collective synthesis failed; using heuristic fallback")
    return _heuristic_synthesis(query, extractions, clusters, ranked_papers=ranked_papers)


async def run_synthesis(
    query: str,
    ranked_papers: list[RankedPaper],
    clusters: list[PaperCluster],
    *,
    llm_config: LLMConfig | None = None,
    handler: EnhancedResponseHandler | None = None,
    concurrency: int = 4,
    session_id: str = "",
    synthesis_config: SynthesisConfig | None = None,
    passages: dict[str, list[str]] | None = None,
) -> tuple[SynthesisResult, list[PaperExtraction], list[PaperAnalysis]]:
    """Run the full two-pass synthesis workflow."""
    if synthesis_config is None:
        from ..config.settings import get_settings

        synthesis_config = get_settings().synthesis

    extractions = await extract_papers(
        ranked_papers,
        query,
        llm_config=llm_config,
        handler=handler,
        concurrency=synthesis_config.concurrency or concurrency,
        session_id=session_id,
        synthesis_config=synthesis_config,
        passages=passages,
    )
    synthesis = await synthesize_collective(
        query,
        extractions,
        clusters,
        ranked_papers=ranked_papers,
        llm_config=llm_config,
        handler=handler,
        session_id=session_id,
        synthesis_config=synthesis_config,
    )
    paper_analyses = _extractions_to_paper_analyses(extractions, ranked_papers)
    return synthesis, extractions, paper_analyses


class SynthesisStage:
    """Pipeline stage that runs two-pass cross-paper synthesis."""

    name = "synthesis"

    def __init__(
        self,
        handler: EnhancedResponseHandler | None = None,
        concurrency: int = 4,
    ) -> None:
        self.handler = handler
        self.concurrency = concurrency

    async def run(
        self,
        ctx: PipelineContext,
        data: list[PaperCluster],
    ) -> StageResult[SynthesisResult]:
        started = time.perf_counter()
        warnings: list[str] = []
        partial = False

        ranked_papers: list[RankedPaper] = ctx.get_artifact("ranked_papers") or []
        if not ranked_papers:
            retrieved = ctx.get_artifact("retrieved_papers") or []
            if retrieved:
                ranked_papers, recovery_warnings = ensure_ranked_papers(
                    retrieved,
                    ctx.query,
                    config=ctx.config.ranking,
                )
                warnings.extend(recovery_warnings)
                ctx.set_artifact("ranked_papers", ranked_papers)

        if not ranked_papers:
            warnings.append("No ranked papers available for synthesis")
            partial = True
            duration_ms = (time.perf_counter() - started) * 1000
            return StageResult(
                output=SynthesisResult(),
                duration_ms=duration_ms,
                warnings=warnings,
                partial=partial,
            )

        try:
            if ctx.config.synthesis.llm_enabled:
                logger.info(
                    "Starting LLM synthesis (top %d papers). "
                    "Set synthesis.llm_enabled=false for fast heuristic mode.",
                    ctx.config.synthesis.max_llm_papers,
                )
            else:
                logger.info("Starting fast heuristic synthesis (no LLM calls)")

            synthesis, extractions, paper_analyses = await run_synthesis(
                ctx.query,
                ranked_papers,
                data,
                passages=ctx.get_artifact("fulltext_passages") or {},
                llm_config=ctx.config.llm,
                handler=self.handler,
                concurrency=ctx.config.synthesis.concurrency,
                session_id=ctx.session.id,
                synthesis_config=ctx.config.synthesis,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
            warnings.append(f"Synthesis timed out or was cancelled: {exc}")
            partial = True
            synthesis = recover_synthesis_output(ctx, data)
            extractions = ctx.get_artifact("paper_extractions") or []
            paper_analyses = ctx.get_artifact("paper_analyses") or []
        except Exception as exc:
            warnings.append(f"Synthesis failed, using heuristic fallback: {exc}")
            partial = True
            extractions = [_heuristic_extraction(paper) for paper in ranked_papers]
            synthesis = _heuristic_synthesis(
                ctx.query,
                extractions,
                data,
                ranked_papers=ranked_papers,
            )
            paper_analyses = _extractions_to_paper_analyses(extractions, ranked_papers)

        ctx.set_artifact("paper_extractions", extractions)
        ctx.set_artifact("paper_analyses", paper_analyses)
        ctx.set_artifact("synthesis_result", synthesis)

        duration_ms = (time.perf_counter() - started) * 1000
        ctx.metrics.custom.setdefault("synthesis", {})
        ctx.metrics.custom["synthesis"] = {
            "papers_extracted": len(extractions),
            "agreements": len(synthesis.agreements),
            "gaps": len(synthesis.gaps),
        }

        return StageResult(
            output=synthesis,
            duration_ms=duration_ms,
            metrics={
                "papers_extracted": len(extractions),
                "agreement_count": len(synthesis.agreements),
                "gap_count": len(synthesis.gaps),
            },
            warnings=warnings,
            partial=partial,
        )
