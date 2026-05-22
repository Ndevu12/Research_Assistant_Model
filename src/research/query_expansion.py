# -*- coding: utf-8 -*-
"""Query expansion via heuristics and optional LLM augmentation."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from ..core.context import PipelineContext, StageResult
from ..retrieval.models import ExpandedQuerySet, QueryUnderstandingResult

if TYPE_CHECKING:
    from ..config.settings import QueryExpansionConfig

DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "machine learning": ["artificial intelligence", "deep learning", "neural networks"],
    "ai": ["artificial intelligence", "machine learning", "automation"],
    "nlp": ["natural language processing", "text analysis", "language models"],
    "natural language processing": ["nlp", "text mining", "language models"],
    "computer vision": ["image processing", "visual recognition", "image analysis"],
    "data science": ["analytics", "big data", "data mining"],
    "transformer": ["attention mechanism", "self-attention", "transformer architecture"],
    "llm": ["large language model", "language model", "generative ai"],
    "reinforcement learning": ["rl", "policy learning", "reward optimization"],
}

ACRONYM_EXPANSIONS: dict[str, str] = {
    "nlp": "natural language processing",
    "cv": "computer vision",
    "rl": "reinforcement learning",
    "llm": "large language model",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "dl": "deep learning",
}

_STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "paper",
    "papers",
    "research",
    "study",
    "studies",
}


def extract_core_concepts(query: str) -> list[str]:
    """Extract core concept terms from a query."""
    words = re.findall(r"\b\w+\b", query.lower())
    return [word for word in words if word not in _STOP_WORDS and len(word) > 3][:5]


def _expand_acronyms(query: str) -> list[str]:
    variants: list[str] = []
    query_lower = query.lower()
    for acronym, expansion in ACRONYM_EXPANSIONS.items():
        pattern = rf"\b{re.escape(acronym)}\b"
        if re.search(pattern, query_lower):
            expanded = re.sub(pattern, expansion, query_lower, flags=re.IGNORECASE)
            if expanded.lower() != query_lower:
                variants.append(expanded)
    return variants


def _expand_synonyms(query: str) -> list[str]:
    variants: list[str] = []
    query_lower = query.lower()
    for term, synonyms in DOMAIN_SYNONYMS.items():
        if term in query_lower:
            for synonym in synonyms:
                variant = query_lower.replace(term, synonym)
                if variant != query_lower:
                    variants.append(variant)
    return variants


def _heuristic_variants(query: str, key_concepts: list[str]) -> list[str]:
    variants: list[str] = []
    variants.extend(_expand_acronyms(query))
    variants.extend(_expand_synonyms(query))

    if key_concepts:
        variants.append(" ".join(key_concepts[:3]))
        if len(key_concepts) >= 2:
            variants.append(f"{key_concepts[0]} {key_concepts[1]} methods")
            variants.append(f"{key_concepts[0]} {key_concepts[1]} applications")

    modifiers = ["recent", "survey", "review"]
    for modifier in modifiers:
        variants.append(f"{modifier} {query}")

    return variants


def _heuristic_sub_questions(query: str, key_concepts: list[str]) -> list[str]:
    concepts = key_concepts or extract_core_concepts(query)
    if not concepts:
        return [f"What are the main approaches to {query}?"]

    primary = concepts[0]
    questions = [
        f"What are the state-of-the-art methods for {primary}?",
        f"How has research on {primary} evolved over time?",
    ]
    if len(concepts) > 1:
        questions.append(
            f"How do {concepts[0]} and {concepts[1]} compare in practice?"
        )
    return questions


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(item.strip())
    return output


def expand_query_heuristic(
    query: str,
    key_concepts: list[str] | None = None,
    max_variants: int = 5,
    max_sub_questions: int = 3,
) -> ExpandedQuerySet:
    """Generate expanded queries using fast heuristic rules."""
    concepts = key_concepts or extract_core_concepts(query)
    variants = _heuristic_variants(query, concepts)
    sub_questions = _heuristic_sub_questions(query, concepts)

    variants = _dedupe_preserve_order(
        [variant for variant in variants if variant.lower() != query.lower()]
    )

    return ExpandedQuerySet(
        original=query,
        variants=variants[:max_variants],
        sub_questions=sub_questions[:max_sub_questions],
    )


async def expand_query_llm(
    query: str,
    config: QueryExpansionConfig,
) -> tuple[list[str], list[str]]:
    """Optional LLM-based query expansion. Returns empty lists when disabled."""
    if not config.llm_enabled:
        return [], []

    try:
        from ..config.settings import get_settings
        from ..models import AgentFactory, AgentRole

        settings = get_settings()
        agent = AgentFactory(settings.llm).create_agent(AgentRole.EXPANSION, config=settings.llm)
        prompt = (
            f"Expand this research query into {config.max_variants} search variants "
            f"and {config.max_sub_questions} sub-questions: {query}"
        )
        from ..utils.progress_reporter import get_progress_reporter, stream_agent_text

        reporter = get_progress_reporter()
        if reporter is not None:
            reporter.set_activity("Expanding query with AI…")

        raw_output = await stream_agent_text(
            agent,
            prompt,
            label="Expanding search queries…",
        )
        import json

        from ..retrieval.helpers_modules.json_extraction import extract_and_clean_json

        payload = json.loads(extract_and_clean_json(raw_output))
        variants = payload.get("variants", [])
        sub_questions = payload.get("sub_questions", [])
        return (
            [str(item) for item in variants][: config.max_variants],
            [str(item) for item in sub_questions][: config.max_sub_questions],
        )
    except Exception:
        return [], []


async def expand_query(
    query: str,
    key_concepts: list[str] | None = None,
    config: QueryExpansionConfig | None = None,
) -> ExpandedQuerySet:
    """Expand a query using heuristics and optional LLM augmentation."""
    if config is None:
        from ..config.settings import get_settings

        config = get_settings().query_expansion

    heuristic = expand_query_heuristic(
        query=query,
        key_concepts=key_concepts,
        max_variants=config.max_variants,
        max_sub_questions=config.max_sub_questions,
    )

    llm_variants, llm_sub_questions = await expand_query_llm(query, config)
    if not llm_variants and not llm_sub_questions:
        return heuristic

    return ExpandedQuerySet(
        original=query,
        variants=_dedupe_preserve_order(heuristic.variants + llm_variants)[: config.max_variants],
        sub_questions=_dedupe_preserve_order(
            heuristic.sub_questions + llm_sub_questions
        )[: config.max_sub_questions],
    )


class QueryExpansionStage:
    """Pipeline stage that expands the user query into variants and sub-questions."""

    name = "query_expansion"

    async def run(
        self,
        ctx: PipelineContext,
        data: str | QueryUnderstandingResult,
    ) -> StageResult[ExpandedQuerySet]:
        started = time.perf_counter()
        warnings: list[str] = []

        if isinstance(data, QueryUnderstandingResult):
            query = ctx.query
            key_concepts = data.key_concepts
        else:
            query = str(data)
            key_concepts = None

        expanded = await expand_query(
            query=query,
            key_concepts=key_concepts,
            config=ctx.config.query_expansion,
        )

        duration_ms = (time.perf_counter() - started) * 1000
        ctx.set_artifact("expanded_queries", expanded)

        return StageResult(
            output=expanded,
            duration_ms=duration_ms,
            metrics={
                "variant_count": len(expanded.variants),
                "sub_question_count": len(expanded.sub_questions),
            },
            warnings=warnings,
        )
