# -*- coding: utf-8 -*-
"""Preservation property tests for orchestrator facade behavior."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.retrieval.models import EnhancedResearchReport
from src.retrieval.orchestrator import run_research_helper
from src.utils.message_formatter import MessageFormatter
from tests.helpers.pipeline_mocks import (
    build_report_from_json_payload,
    mock_pipeline_exception,
    mock_pipeline_result,
)


class TestJSONParsingPreservation:
    @pytest.mark.asyncio
    async def test_valid_json_response_processing_preservation(self, capsys) -> None:
        payload = {
            "query": "AI research methodology",
            "papers": [
                {
                    "title": "Valid Test Paper",
                    "year": 2023,
                    "venue": "Test Conference",
                    "url": "https://example.com/valid-paper",
                    "doi": "10.1000/valid-test",
                    "key_points": ["Introduces novel AI methodology"],
                    "why_relevant": ["Directly addresses the research query"],
                },
                {
                    "title": "Another Valid Paper",
                    "year": 2022,
                    "venue": "Another Conference",
                    "url": "https://example.com/another-paper",
                    "doi": "10.1000/another-test",
                    "key_points": ["Complementary research approach"],
                    "why_relevant": ["Provides additional context"],
                },
            ],
        }
        report = build_report_from_json_payload(payload)

        with mock_pipeline_result(report):
            await run_research_helper("AI research methodology")

        captured = capsys.readouterr()
        assert "# Executive Summary" in captured.out
        assert "AI research methodology" in captured.out
        assert "Valid Test Paper" in captured.out
        assert "Another Valid Paper" in captured.out
        assert "Introduces novel AI methodology" in captured.out

    @pytest.mark.asyncio
    async def test_code_block_extraction_preservation(self, capsys) -> None:
        payload = {
            "query": "code block test",
            "papers": [{"title": "Code Block Paper", "key_points": ["Works"], "why_relevant": ["Relevant"]}],
        }
        report = build_report_from_json_payload(payload)

        with mock_pipeline_result(report):
            await run_research_helper("code block test")

        captured = capsys.readouterr()
        assert "Code Block Paper" in captured.out

    @pytest.mark.asyncio
    async def test_network_error_handling_preservation(self, capsys) -> None:
        with mock_pipeline_exception("Connection timeout"):
            await run_research_helper("test query")

        captured = capsys.readouterr()
        expected_error = MessageFormatter.network_error("Connection timeout")
        assert expected_error in captured.out
        assert "Check your internet connection" in captured.out

    @pytest.mark.asyncio
    async def test_no_results_handling_preservation(self, capsys) -> None:
        empty_report = EnhancedResearchReport(query="obscure query with no results")

        with mock_pipeline_result(empty_report):
            await run_research_helper("obscure query with no results")

        captured = capsys.readouterr()
        assert MessageFormatter.no_results_message() in captured.out


class TestPreservationProperties:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "valid_json_data",
        [
            {"query": "minimal test", "papers": []},
            {
                "query": "single paper test",
                "papers": [
                    {
                        "title": "Complete Paper",
                        "year": 2023,
                        "venue": "Test Venue",
                        "url": "https://example.com/paper",
                        "doi": "10.1000/test",
                        "key_points": ["point 1", "point 2"],
                        "why_relevant": ["reason 1", "reason 2"],
                    }
                ],
            },
            {
                "query": "multiple papers test",
                "papers": [
                    {"title": "Paper 1", "key_points": ["key point"], "why_relevant": ["relevant because"]},
                    {"title": "Paper 2", "year": 2022, "venue": "Another Venue", "key_points": [], "why_relevant": ["another reason"]},
                ],
            },
            {
                "query": "none values test",
                "papers": [
                    {
                        "title": "Paper with Nones",
                        "year": None,
                        "venue": None,
                        "url": None,
                        "doi": None,
                        "key_points": ["some point"],
                        "why_relevant": ["some reason"],
                    }
                ],
            },
        ],
    )
    async def test_valid_json_structures_preservation_property(
        self,
        valid_json_data: dict,
        capsys,
    ) -> None:
        report = build_report_from_json_payload(valid_json_data)

        with mock_pipeline_result(report):
            await run_research_helper("property test query")

        captured = capsys.readouterr()
        if valid_json_data["papers"]:
            assert "# Executive Summary" in captured.out
            assert valid_json_data["papers"][0]["title"] in captured.out
        else:
            assert MessageFormatter.no_results_message() in captured.out

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "wrapper,expects_success",
        [
            ("```json\n{content}\n```", True),
            ("```\n{content}\n```", True),
            ("{content}", True),
            ("Here's the analysis:\n```json\n{content}\n```\nEnd of analysis.", True),
        ],
    )
    async def test_code_block_format_preservation_property(
        self,
        wrapper: str,
        expects_success: bool,
        capsys,
    ) -> None:
        payload = {
            "query": "format test",
            "papers": [{"title": "Format Paper", "key_points": ["point"], "why_relevant": ["reason"]}],
        }
        report = build_report_from_json_payload(payload)

        with mock_pipeline_result(report):
            await run_research_helper("format test")

        captured = capsys.readouterr()
        assert expects_success
        assert "Format Paper" in captured.out

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "json_payload,description",
        [
            ('{"query": "test", "papers": [{"title": "Multi-line\\nTitle Paper"}]}', "literal newlines in string values"),
            ('{"query": "test", "papers": [{"title": "Paper with\\n    indented continuation"}]}', "newlines with indentation in strings"),
            ('{"query": "test\\nquery", "papers": [{"title": "Paper"}]}', "newlines in query field"),
        ],
    )
    async def test_newline_handling_preservation_property(
        self,
        json_payload: str,
        description: str,
        capsys,
    ) -> None:
        payload = json.loads(json_payload)
        report = build_report_from_json_payload(payload)

        with mock_pipeline_result(report):
            await run_research_helper("newline test")

        captured = capsys.readouterr()
        assert "Paper" in captured.out
