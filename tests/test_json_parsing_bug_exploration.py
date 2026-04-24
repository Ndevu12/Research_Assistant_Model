# -*- coding: utf-8 -*-
"""Bug condition exploration test for JSON parsing error fix.

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists.
This test encodes the expected behavior and will validate the fix when it passes after implementation.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio

from src.retrieval.orchestrator import run_research_helper
from src.retrieval.models import RetrievedPaper


class TestJSONParsingBugCondition:
    """Test cases that demonstrate the JSON parsing bug on unfixed code.
    
    These tests are EXPECTED TO FAIL on unfixed code, confirming the bug exists.
    When the fix is implemented, these same tests should PASS.
    """

    @pytest.fixture
    def mock_papers(self):
        """Mock papers for testing."""
        return [
            RetrievedPaper(
                title="Test Paper 1",
                abstract="Test abstract 1",
                year=2023,
                venue="Test Venue",
                url="https://example.com/paper1",
                doi="10.1000/test1",
                source="test"
            )
        ]

    @pytest.fixture
    def mock_successful_search(self, mock_papers):
        """Mock successful paper search to isolate JSON parsing testing."""
        async def mock_openalex(*args, **kwargs):
            return mock_papers
        
        async def mock_s2(*args, **kwargs):
            return []
            
        with patch('src.retrieval.orchestrator.search_openalex', side_effect=mock_openalex), \
             patch('src.retrieval.orchestrator.search_semantic_scholar', side_effect=mock_s2):
            yield

    @pytest.mark.asyncio
    async def test_malformed_json_syntax_error_handling(self, mock_successful_search, capsys):
        """Test that malformed JSON with syntax errors is handled gracefully.
        
        **Property 1: Bug Condition** - JSON Parsing Failure Handling
        **Validates: Requirements 1.1, 2.1**
        
        EXPECTED ON UNFIXED CODE: Test FAILS (application crashes with JSON parsing exception)
        EXPECTED ON FIXED CODE: Test PASSES (graceful error handling with meaningful message)
        """
        # Mock LLM response with trailing comma syntax error
        malformed_json_response = '''```json
{
    "query": "AI research",
    "papers": [
        {
            "title": "Test Paper",
            "key_points": ["point 1", "point 2",],
            "why_relevant": ["relevant because"]
        }
    ]
}```'''

        mock_result = MagicMock()
        mock_result.output = malformed_json_response

        with patch('src.retrieval.orchestrator.analysis_agent') as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            
            # This should NOT crash the application
            await run_research_helper("test query")
            
            captured = capsys.readouterr()
            
            # Expected behavior: graceful error handling
            assert "❌ Error: Parsing Error:" in captured.out, "Should display meaningful error message"
            assert "-- RAW RESPONSE FROM LLM --" in captured.out, "Should show raw response for debugging"
            assert malformed_json_response in captured.out, "Should display the actual malformed response"
            
            # Should NOT contain successful research report
            assert "Test Paper" not in captured.out or "❌ Error:" in captured.out, "Should not display successful report when parsing fails"

    @pytest.mark.asyncio
    async def test_missing_required_fields_handling(self, mock_successful_search, capsys):
        """Test that JSON with missing required fields is handled gracefully.
        
        **Property 1: Bug Condition** - JSON Parsing Failure Handling  
        **Validates: Requirements 1.2, 2.2**
        
        EXPECTED ON UNFIXED CODE: Test FAILS (application crashes with validation error)
        EXPECTED ON FIXED CODE: Test PASSES (graceful error handling with field-specific message)
        """
        # Mock LLM response missing "query" field
        missing_query_response = '''```json
{
    "papers": [
        {
            "title": "Test Paper",
            "key_points": ["point 1"],
            "why_relevant": ["relevant"]
        }
    ]
}```'''

        mock_result = MagicMock()
        mock_result.output = missing_query_response

        with patch('src.retrieval.orchestrator.analysis_agent') as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            
            # This should NOT crash the application
            await run_research_helper("test query")
            
            captured = capsys.readouterr()
            
            # Expected behavior: graceful error handling with field-specific feedback
            assert "❌ Error: Parsing Error:" in captured.out, "Should display meaningful error message"
            assert "-- RAW RESPONSE FROM LLM --" in captured.out, "Should show raw response for debugging"
            assert missing_query_response in captured.out, "Should display the actual response"

    @pytest.mark.asyncio
    async def test_invalid_data_types_handling(self, mock_successful_search, capsys):
        """Test that JSON with invalid data types is handled gracefully.
        
        **Property 1: Bug Condition** - JSON Parsing Failure Handling
        **Validates: Requirements 1.2, 2.2**
        
        EXPECTED ON UNFIXED CODE: Test FAILS (application crashes with validation error)  
        EXPECTED ON FIXED CODE: Test PASSES (graceful error handling with type-specific message)
        """
        # Mock LLM response where "papers" is not a list
        invalid_type_response = '''```json
{
    "query": "AI research",
    "papers": "not a list but a string"
}```'''

        mock_result = MagicMock()
        mock_result.output = invalid_type_response

        with patch('src.retrieval.orchestrator.analysis_agent') as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            
            # This should NOT crash the application
            await run_research_helper("test query")
            
            captured = capsys.readouterr()
            
            # Expected behavior: graceful error handling
            assert "❌ Error: Parsing Error:" in captured.out, "Should display meaningful error message"
            assert "-- RAW RESPONSE FROM LLM --" in captured.out, "Should show raw response for debugging"
            assert invalid_type_response in captured.out, "Should display the actual response"

    @pytest.mark.asyncio
    async def test_non_json_conversational_response_handling(self, mock_successful_search, capsys):
        """Test that non-JSON conversational responses are handled gracefully.
        
        **Property 1: Bug Condition** - JSON Parsing Failure Handling
        **Validates: Requirements 1.3, 2.3**
        
        EXPECTED ON UNFIXED CODE: Test FAILS (application crashes during JSON parsing)
        EXPECTED ON FIXED CODE: Test PASSES (graceful error handling with appropriate message)
        """
        # Mock LLM response with conversational text instead of JSON
        conversational_response = """I found some interesting papers for you about AI research:

1. "Deep Learning Advances" - This paper discusses recent developments in neural networks
2. "Machine Learning Applications" - Covers practical applications of ML in industry

These papers are relevant because they address the core concepts you're researching."""

        mock_result = MagicMock()
        mock_result.output = conversational_response

        with patch('src.retrieval.orchestrator.analysis_agent') as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            
            # This should NOT crash the application
            await run_research_helper("test query")
            
            captured = capsys.readouterr()
            
            # Expected behavior: graceful error handling
            assert "❌ Error: Parsing Error:" in captured.out, "Should display meaningful error message"
            assert "-- RAW RESPONSE FROM LLM --" in captured.out, "Should show raw response for debugging"
            assert conversational_response in captured.out, "Should display the actual response"

    @pytest.mark.asyncio
    async def test_application_continues_after_parsing_failure(self, mock_successful_search, capsys):
        """Test that the application continues running after JSON parsing failures.
        
        **Property 1: Bug Condition** - JSON Parsing Failure Handling
        **Validates: Requirements 1.4, 2.4**
        
        EXPECTED ON UNFIXED CODE: Test FAILS (application crashes and cannot continue)
        EXPECTED ON FIXED CODE: Test PASSES (application handles error and continues operation)
        """
        # Mock LLM response with malformed JSON
        malformed_response = '{"query": "test", "papers": [invalid json}'

        mock_result = MagicMock()
        mock_result.output = malformed_response

        with patch('src.retrieval.orchestrator.analysis_agent') as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            
            # The function should complete without raising an exception
            try:
                await run_research_helper("test query")
                # If we reach here, the function completed successfully (expected behavior)
                function_completed = True
            except Exception as e:
                # If an exception is raised, the application crashed (bug behavior)
                function_completed = False
                pytest.fail(f"Application crashed with exception: {e}")
            
            assert function_completed, "Function should complete without crashing"
            
            captured = capsys.readouterr()
            
            # Should show error handling, not crash
            assert "❌ Error: Parsing Error:" in captured.out, "Should display error message instead of crashing"
            assert "-- RAW RESPONSE FROM LLM --" in captured.out, "Should show raw response for debugging"


# Property-based test for scoped approach to deterministic bugs
class TestScopedBugConditionProperty:
    """Property-based test scoped to concrete failing cases for reproducibility."""

    @pytest.fixture
    def mock_papers(self):
        """Mock papers for testing."""
        return [
            RetrievedPaper(
                title="Test Paper",
                abstract="Test abstract",
                year=2023,
                venue="Test Venue", 
                url="https://example.com/paper",
                doi="10.1000/test",
                source="test"
            )
        ]

    @pytest.fixture
    def mock_successful_search(self, mock_papers):
        """Mock successful paper search."""
        async def mock_openalex(*args, **kwargs):
            return mock_papers
        
        async def mock_s2(*args, **kwargs):
            return []
            
        with patch('src.retrieval.orchestrator.search_openalex', side_effect=mock_openalex), \
             patch('src.retrieval.orchestrator.search_semantic_scholar', side_effect=mock_s2):
            yield

    @pytest.mark.asyncio
    @pytest.mark.parametrize("malformed_response,error_description", [
        # Syntax errors
        ('{"query": "test", "papers": [{"title": "Paper",}]}', "trailing comma"),
        ('{"query": "test", "papers": [{"title": "Paper"}', "missing closing bracket"),
        ('{"query": "test" "papers": []}', "missing comma between fields"),
        
        # Missing required fields  
        ('{"papers": [{"title": "Paper"}]}', "missing query field"),
        ('{"query": "test"}', "missing papers field"),
        ('{}', "missing both required fields"),
        
        # Invalid data types
        ('{"query": "test", "papers": "not a list"}', "papers not a list"),
        ('{"query": 123, "papers": []}', "query not a string"),
        ('{"query": "test", "papers": {"title": "Paper"}}', "papers is object not list"),
        
        # Non-JSON responses
        ('Just some text without JSON structure', "plain text response"),
        ('```\nSome code but not JSON\n```', "code block without JSON"),
        ('I found papers: Paper 1, Paper 2', "conversational response"),
    ])
    async def test_malformed_json_handling_property(self, mock_successful_search, malformed_response, error_description, capsys):
        """Property-based test for malformed JSON handling across concrete failing cases.
        
        **Property 1: Bug Condition** - JSON Parsing Failure Handling
        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4**
        
        This property test covers the concrete failing cases to ensure reproducibility
        while testing the universal property that ALL malformed JSON should be handled gracefully.
        
        EXPECTED ON UNFIXED CODE: Test FAILS (crashes with various JSON/validation exceptions)
        EXPECTED ON FIXED CODE: Test PASSES (graceful error handling for all cases)
        """
        mock_result = MagicMock()
        mock_result.output = malformed_response

        with patch('src.retrieval.orchestrator.analysis_agent') as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            
            # The function should NOT crash regardless of malformed input
            try:
                await run_research_helper("test query")
                function_completed = True
            except Exception as e:
                function_completed = False
                pytest.fail(f"Application crashed on {error_description} with exception: {e}")
            
            assert function_completed, f"Function should complete without crashing on {error_description}"
            
            captured = capsys.readouterr()
            
            # Universal property: ALL malformed JSON should result in graceful error handling
            assert "❌ Error: Parsing Error:" in captured.out, f"Should display error message for {error_description}"
            assert "-- RAW RESPONSE FROM LLM --" in captured.out, f"Should show raw response for debugging {error_description}"
            assert malformed_response in captured.out, f"Should display the actual malformed response for {error_description}"