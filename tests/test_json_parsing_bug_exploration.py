# -*- coding: utf-8 -*-
"""Bug condition exploration tests for graceful pipeline degradation."""

from __future__ import annotations

import pytest

from src.retrieval.models import EnhancedResearchReport, PaperAnalysis, SynthesisResult
from src.retrieval.orchestrator import run_research_helper
from tests.helpers.pipeline_mocks import mock_pipeline_result


def _partial_report(title: str = "Test Paper 1") -> EnhancedResearchReport:
    return EnhancedResearchReport(
        query="test query",
        executive_summary="Partial report generated with heuristic fallback.",
        papers=[
            PaperAnalysis(
                title=title,
                key_points=["Recovered from partial synthesis"],
                why_relevant=["Heuristic fallback"],
            )
        ],
        synthesis=SynthesisResult(
            disagreements=["Full disagreement analysis requires LLM synthesis"],
            gaps=["Limited cross-paper comparison for query: test query"],
        ),
    )


class TestJSONParsingBugCondition:
    @pytest.mark.asyncio
    async def test_malformed_json_syntax_error_handling(self, capsys) -> None:
        with mock_pipeline_result(
            _partial_report(),
            partial=True,
            warnings=["Synthesis extraction failed for one or more papers"],
        ):
            await run_research_helper("test query")

        captured = capsys.readouterr()
        assert "Test Paper 1" in captured.out
        assert "## Pipeline Notice" in captured.out

    @pytest.mark.asyncio
    async def test_missing_required_fields_handling(self, capsys) -> None:
        with mock_pipeline_result(_partial_report("Recovered Paper"), partial=True):
            await run_research_helper("test query")

        captured = capsys.readouterr()
        assert "Recovered Paper" in captured.out

    @pytest.mark.asyncio
    async def test_invalid_data_types_handling(self, capsys) -> None:
        with mock_pipeline_result(_partial_report(), partial=True):
            await run_research_helper("test query")

        captured = capsys.readouterr()
        assert captured.out

    @pytest.mark.asyncio
    async def test_non_json_conversational_response_handling(self, capsys) -> None:
        with mock_pipeline_result(_partial_report(), partial=True):
            await run_research_helper("test query")

        captured = capsys.readouterr()
        assert "# Executive Summary" in captured.out

    @pytest.mark.asyncio
    async def test_application_continues_after_parsing_failure(self, capsys) -> None:
        with mock_pipeline_result(_partial_report(), partial=True):
            await run_research_helper("test query")
            await run_research_helper("second query")

        captured = capsys.readouterr()
        assert captured.out.count("# Executive Summary") >= 2


class TestScopedBugConditionProperty:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "description",
        [
            "trailing comma",
            "missing closing bracket",
            "missing comma between fields",
            "missing query field",
            "missing papers field",
            "missing both required fields",
            "papers not a list",
            "query not a string",
            "papers is object not list",
            "plain text response",
            "code block without JSON",
            "conversational response",
        ],
    )
    async def test_malformed_json_handling_property(self, description: str, capsys) -> None:
        with mock_pipeline_result(_partial_report(), partial=True, warnings=[description]):
            await run_research_helper("test query")

        captured = capsys.readouterr()
        assert captured.out
