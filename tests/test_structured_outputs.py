# -*- coding: utf-8 -*-
"""Tests for schema-enforced LLM calls (native structured outputs)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field
from pydantic_ai.models.test import TestModel

from src.analysis.gap_analysis import analyze_gaps
from src.analysis.synthesis import extract_papers, synthesize_collective
from src.config.settings import AppSettings, LLMConfig
from src.models.base import AgentRole
from src.models.structured import (
    STRUCTURED_ROLE_PROMPTS,
    run_structured,
    try_run_structured,
)
from src.retrieval.models import (
    GapAnalysisResult,
    PaperExtraction,
    RankedPaper,
    RetrievedPaper,
    SynthesisResult,
)


class _Sample(BaseModel):
    items: list[str] = Field(default_factory=list)
    note: str = ""


def _ranked(title: str, abstract: str = "Findings here.") -> RankedPaper:
    return RankedPaper(
        paper=RetrievedPaper(title=title, abstract=abstract, provider="test"),
        rank_score=0.8,
        score_breakdown={},
    )


def _structured_llm() -> LLMConfig:
    return LLMConfig(structured_outputs=True)


class TestRunStructured:
    async def test_returns_schema_valid_output_with_test_model(self) -> None:
        result = await run_structured(
            AgentRole.EXTRACTION,
            "extract this",
            _Sample,
            model=TestModel(),
        )

        assert isinstance(result, _Sample)

    async def test_try_run_structured_returns_none_on_model_failure(self) -> None:
        from pydantic_ai.models.function import FunctionModel

        def exploding(messages, info):
            raise RuntimeError("backend down")

        result = await try_run_structured(
            AgentRole.SYNTHESIS,
            "synthesize",
            _Sample,
            model=FunctionModel(exploding),
        )

        assert result is None

    def test_all_llm_roles_have_slim_structured_prompts(self) -> None:
        for role in (
            AgentRole.EXPANSION,
            AgentRole.EXTRACTION,
            AgentRole.SYNTHESIS,
            AgentRole.GAP_ANALYSIS,
        ):
            prompt = STRUCTURED_ROLE_PROMPTS[role]
            assert "JSON" not in prompt  # schema is enforced natively


class TestStructuredExtraction:
    async def test_extraction_uses_structured_path_and_pins_identity(self) -> None:
        ranked = [_ranked("Real Title")]
        hallucinated = PaperExtraction(
            paper_id="made-up-id",
            title="Hallucinated Title",
            findings=["A finding"],
        )

        async def fake_structured(role, prompt, output_type, config=None, **kwargs):
            assert role is AgentRole.EXTRACTION
            return hallucinated

        with patch("src.models.structured.try_run_structured", side_effect=fake_structured):
            extractions = await extract_papers(
                ranked,
                "query",
                llm_config=_structured_llm(),
                synthesis_config=AppSettings(
                    synthesis={"llm_enabled": True, "max_llm_papers": 1}
                ).synthesis,
            )

        assert extractions[0].paper_id == ranked[0].paper.paper_id
        assert extractions[0].title == "Real Title"
        assert extractions[0].findings == ["A finding"]

    async def test_structured_failure_falls_back_and_trips_breaker(self) -> None:
        ranked = [_ranked(f"Paper {i}") for i in range(4)]

        calls = {"count": 0}

        async def failing_structured(*args, **kwargs):
            calls["count"] += 1
            return None

        with patch("src.models.structured.try_run_structured", side_effect=failing_structured):
            extractions = await extract_papers(
                ranked,
                "query",
                llm_config=_structured_llm(),
                concurrency=1,
                synthesis_config=AppSettings(
                    synthesis={
                        "llm_enabled": True,
                        "max_llm_papers": 4,
                        "circuit_breaker_failures": 2,
                        "concurrency": 1,
                    }
                ).synthesis,
            )

        assert len(extractions) == 4
        # Breaker opens after 2 failures; remaining papers skip the LLM.
        assert calls["count"] == 2
        assert all("abstract" in e.methodology[0] for e in extractions)


class TestStructuredSynthesisAndGaps:
    async def test_collective_synthesis_structured_path(self) -> None:
        expected = SynthesisResult(agreements=["Agreement"], gaps=["Gap"])

        async def fake_structured(role, prompt, output_type, config=None, **kwargs):
            assert role is AgentRole.SYNTHESIS
            assert output_type is SynthesisResult
            return expected

        with patch("src.models.structured.try_run_structured", side_effect=fake_structured):
            result = await synthesize_collective(
                "query",
                [PaperExtraction(paper_id="a", title="A", findings=["F"])],
                [],
                llm_config=_structured_llm(),
                synthesis_config=AppSettings(
                    synthesis={"llm_enabled": True}
                ).synthesis,
            )

        assert result is expected

    async def test_gap_analysis_structured_path(self) -> None:
        expected = GapAnalysisResult(gaps=["G"], opportunities=["O"])

        async def fake_structured(role, prompt, output_type, config=None, **kwargs):
            assert role is AgentRole.GAP_ANALYSIS
            return expected

        with patch("src.models.structured.try_run_structured", side_effect=fake_structured):
            result = await analyze_gaps(
                "query",
                SynthesisResult(gaps=["G"]),
                llm_config=_structured_llm(),
            )

        assert result is expected

    async def test_gap_analysis_structured_failure_uses_heuristics(self) -> None:
        async def failing(*args, **kwargs):
            return None

        with patch("src.models.structured.try_run_structured", side_effect=failing):
            result = await analyze_gaps(
                "query",
                SynthesisResult(gaps=["Known gap"]),
                llm_config=_structured_llm(),
            )

        assert "Known gap" in result.gaps


class TestStructuredExpansion:
    async def test_expansion_uses_structured_output(self, monkeypatch) -> None:
        from src.research.query_expansion import _ExpansionSuggestions, expand_query_llm
        from src.config.settings import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("RA_LLM__STRUCTURED_OUTPUTS", "true")

        async def fake_run(role, prompt, output_type, config=None, **kwargs):
            assert role is AgentRole.EXPANSION
            return _ExpansionSuggestions(
                variants=["variant one", "variant two"],
                sub_questions=["sub question"],
            )

        try:
            with patch("src.models.structured.run_structured", side_effect=fake_run):
                variants, sub_questions = await expand_query_llm(
                    "test query",
                    AppSettings(
                        query_expansion={
                            "llm_enabled": True,
                            "max_variants": 2,
                            "max_sub_questions": 1,
                        }
                    ).query_expansion,
                )
        finally:
            get_settings.cache_clear()

        assert variants == ["variant one", "variant two"]
        assert sub_questions == ["sub question"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
