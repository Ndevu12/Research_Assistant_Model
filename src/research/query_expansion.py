# -*- coding: utf-8 -*-
"""Query expansion via heuristics and optional LLM augmentation."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ..core.context import PipelineContext, StageResult
from ..retrieval.models import ExpandedQuerySet, QueryUnderstandingResult
from .text_utils import QUERY_STOP_WORDS, extract_core_concepts


class _ExpansionSuggestions(BaseModel):
    """Structured output for LLM query expansion."""

    variants: list[str] = Field(default_factory=list)
    sub_questions: list[str] = Field(default_factory=list)

if TYPE_CHECKING:
    from ..config.settings import QueryExpansionConfig

__all__ = [
    "extract_core_concepts",
    "expand_query_heuristic",
    "QueryExpansionStage",
    "DOMAIN_SYNONYMS",
    "ACRONYM_EXPANSIONS",
]

DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "machine learning": ["artificial intelligence", "deep learning", "neural networks"],
    "ai": ["artificial intelligence", "machine learning", "automation"],
    "nlp": ["natural language processing", "text analysis", "language models"],
    "natural language processing": ["nlp", "text mining", "language models"],
    "computer vision": ["image processing", "visual recognition", "image analysis"],
    "data science": ["analytics", "big data", "data mining"],
    "self-attention": ["scaled dot-product attention", "multi-head attention"],
    "attention mechanism": ["self-attention", "scaled dot-product attention"],
    "attention mechanisms": ["self-attention mechanisms", "multi-head attention"],
    "transformer": ["self-attention", "transformer architecture", "attention mechanism"],
    "llm": ["large language model", "language model", "generative ai"],
    "reinforcement learning": ["rl", "policy learning", "reward optimization"],
}

_BROAD_SINGLE_CONCEPT_TERMS = frozenset(
    {"attention", "transformer", "learning", "model", "models", "network", "networks"}
)

_VARIANT_MIN_JACCARD = 0.3

ACRONYM_EXPANSIONS: dict[str, str] = {
    "nlp": "natural language processing",
    "cv": "computer vision",
    "rl": "reinforcement learning",
    "llm": "large language model",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "dl": "deep learning",
}

def _token_set(text: str) -> set[str]:
    return set(re.findall(r"\b\w+\b", text.lower()))


def _bigrams(text: str) -> set[tuple[str, str]]:
    words = re.findall(r"\b\w+\b", text.lower())
    return {(words[index], words[index + 1]) for index in range(len(words) - 1)}


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def _phrase_in_text(phrase: str, text: str) -> bool:
    pattern = rf"\b{re.escape(phrase)}\b"
    return bool(re.search(pattern, text, flags=re.IGNORECASE))


def _normalize_concept_token(token: str) -> str:
    if token.endswith("s") and len(token) > 4:
        return token[:-1]
    return token


def _normalized_token_set(text: str) -> set[str]:
    return {_normalize_concept_token(token) for token in _token_set(text)}


def _synonym_already_in_query(synonym: str, query: str) -> bool:
    if _phrase_in_text(synonym, query):
        return True
    synonym_tokens = _normalized_token_set(synonym)
    query_tokens = _normalized_token_set(query)
    return bool(synonym_tokens) and synonym_tokens <= query_tokens


def _replacement_is_redundant(query: str, term: str, synonym: str) -> bool:
    if _synonym_already_in_query(synonym, query):
        return True
    remainder = re.sub(r"\s+", " ", _replace_phrase(query, term, " ")).strip()
    if not remainder:
        return False
    synonym_tokens = _normalized_token_set(synonym)
    remainder_tokens = _normalized_token_set(remainder)
    if not synonym_tokens:
        return False
    overlap = synonym_tokens & remainder_tokens
    return len(overlap) >= max(1, len(synonym_tokens) - 1)


def _replace_phrase(text: str, old: str, new: str) -> str:
    pattern = rf"\b{re.escape(old)}\b"
    return re.sub(pattern, new, text, flags=re.IGNORECASE)


def _passes_variant_quality_gate(original: str, variant: str) -> bool:
    original_tokens = _token_set(original)
    variant_tokens = _token_set(variant)
    if _jaccard_similarity(original_tokens, variant_tokens) >= _VARIANT_MIN_JACCARD:
        return True
    return bool(_bigrams(variant) - _bigrams(original))


def _matched_concept_count(variant: str, key_concepts: list[str]) -> int:
    variant_lower = variant.lower()
    return sum(1 for concept in key_concepts if concept.lower() in variant_lower)


def _passes_broad_term_guard(
    variant: str,
    key_concepts: list[str],
) -> bool:
    if len(key_concepts) < 2:
        return True

    variant_tokens = _token_set(variant) - QUERY_STOP_WORDS
    if len(variant_tokens) == 1 and variant_tokens & _BROAD_SINGLE_CONCEPT_TERMS:
        return False

    return _matched_concept_count(variant, key_concepts) >= 2


def _filter_variants(
    original: str,
    variants: list[str],
    key_concepts: list[str],
) -> list[str]:
    filtered: list[str] = []
    original_lower = original.lower()
    for variant in variants:
        normalized = variant.strip()
        if not normalized:
            continue
        if normalized.lower() == original_lower:
            continue
        if not _passes_variant_quality_gate(original, normalized):
            continue
        if not _passes_broad_term_guard(normalized, key_concepts):
            continue
        filtered.append(normalized)
    return filtered


def _expand_acronyms(query: str) -> list[str]:
    variants: list[str] = []
    query_lower = query.lower()
    for acronym, expansion in ACRONYM_EXPANSIONS.items():
        pattern = rf"\b{re.escape(acronym)}\b"
        if re.search(pattern, query_lower):
            expanded = re.sub(pattern, expansion, query, flags=re.IGNORECASE)
            if expanded.lower() != query_lower:
                variants.append(expanded)
    return variants


def _expand_synonyms(query: str) -> list[str]:
    variants: list[str] = []
    query_lower = query.lower()
    sorted_terms = sorted(DOMAIN_SYNONYMS, key=len, reverse=True)

    for term in sorted_terms:
        if not _phrase_in_text(term, query_lower):
            continue
        for synonym in DOMAIN_SYNONYMS[term]:
            if _replacement_is_redundant(query_lower, term, synonym):
                continue
            variant = _replace_phrase(query, term, synonym)
            if variant.lower() != query_lower:
                variants.append(variant)
    return variants


def _heuristic_variants(query: str, key_concepts: list[str]) -> list[str]:
    core_variants: list[str] = []
    core_variants.extend(_expand_acronyms(query))
    core_variants.extend(_expand_synonyms(query))
    variants = _filter_variants(query, core_variants, key_concepts)

    if key_concepts:
        concept_join = " ".join(key_concepts[:3])
        if concept_join.lower() != query.lower():
            variants.append(concept_join)
        if len(key_concepts) >= 2:
            variants.append(f"{key_concepts[0]} {key_concepts[1]} methods")
            variants.append(f"{key_concepts[0]} {key_concepts[1]} applications")

    modifiers = ["recent", "survey", "review"]
    for modifier in modifiers:
        variants.append(f"{modifier} {query}")

    return _filter_variants(query, variants, key_concepts)


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

    variants = _dedupe_preserve_order(variants)

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
        from ..models import AgentRole
        from ..models.structured import run_structured
        from ..utils.progress_reporter import get_progress_reporter

        settings = get_settings()
        prompt = (
            f"Expand this research query into {config.max_variants} search variants "
            f"and {config.max_sub_questions} sub-questions: {query}"
        )

        reporter = get_progress_reporter()
        if reporter is not None:
            reporter.set_activity("Expanding query with AI…")

        suggestions = await run_structured(
            AgentRole.EXPANSION,
            prompt,
            _ExpansionSuggestions,
            settings.llm,
        )
        return (
            [str(item) for item in suggestions.variants][: config.max_variants],
            [str(item) for item in suggestions.sub_questions][
                : config.max_sub_questions
            ],
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
