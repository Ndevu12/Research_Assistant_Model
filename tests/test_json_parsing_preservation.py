# -*- coding: utf-8 -*-
"""Preservation property tests for JSON parsing error fix.

**IMPORTANT**: Follow observation-first methodology.
These tests capture the baseline behavior on UNFIXED code for valid JSON responses.
They ensure the fix doesn't break existing functionality.

**Property 2: Preservation** - Valid JSON Response Processing
**Validates: Requirements 3.1, 3.2, 3.3, 3.4**
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio

from src.retrieval.orchestrator import run_research_helper
from src.retrieval.models import RetrievedPaper
from src.utils.message_formatter import MessageFormatter


class TestJSONParsingPreservation:
    """Test cases that verify existing functionality is preserved after the fix.
    
    These tests should PASS on both unfixed and fixed code, ensuring no regressions.
    """

    @pytest.fixture
    def mock_papers(self):
        """Mock papers for testing."""
        return [
            RetrievedPaper(
                title="Valid Test Paper",
                abstract="This is a valid test abstract for preservation testing.",
                year=2023,
                venue="Test Conference",
                url="https://example.com/valid-paper",
                doi="10.1000/valid-test",
                source="test"
            ),
            RetrievedPaper(
                title="Another Valid Paper",
                abstract="Another valid abstract for comprehensive testing.",
                year=2022,
                venue="Another Conference",
                url="https://example.com/another-paper",
                doi="10.1000/another-test",
                source="test"
            )
        ]

    @pytest.fixture
    def mock_successful_search(self, mock_papers):
        """Mock successful paper search to isolate JSON processing testing."""
        async def mock_openalex(*args, **kwargs):
            return mock_papers
        
        async def mock_s2(*args, **kwargs):
            return []
            
        with patch('src.retrieval.orchestrator.search_openalex', side_effect=mock_openalex), \
             patch('src.retrieval.orchestrator.search_semantic_scholar', side_effect=mock_s2):
            yield

    @pytest.mark.asyncio
    async def test_valid_json_response_processing_preservation(self, mock_successful_search, capsys):
        """Test that well-formed JSON responses continue to work correctly.
        
        **Property 2: Preservation** - Valid JSON Response Processing
        **Validates: Requirements 3.1**
        
        EXPECTED ON UNFIXED CODE: Test PASSES (successful research report generation)
        EXPECTED ON FIXED CODE: Test PASSES (same successful behavior preserved)
        """
        # Mock valid LLM response with correct structure
        valid_json_response = '''```json
{
    "query": "AI research methodology",
    "papers": [
        {
            "title": "Valid Test Paper",
            "year": 2023,
            "venue": "Test Conference",
            "url": "https://example.com/valid-paper",
            "doi": "10.1000/valid-test",
            "key_points": [
                "Introduces novel AI methodology",
                "Comprehensive experimental validation",
                "Significant performance improvements"
            ],
            "why_relevant": [
                "Directly addresses the research query",
                "Provides methodological framework",
                "Recent and highly cited work"
            ]
        },
        {
            "title": "Another Valid Paper", 
            "year": 2022,
            "venue": "Another Conference",
            "url": "https://example.com/another-paper",
            "doi": "10.1000/another-test",
            "key_points": [
                "Complementary research approach",
                "Extensive literature review"
            ],
            "why_relevant": [
                "Provides additional context",
                "Supports main research direction"
            ]
        }
    ]
}```'''

        mock_result = MagicMock()
        mock_result.output = valid_json_response

        with patch('src.retrieval.orchestrator.analysis_agent') as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            
            # This should work successfully
            await run_research_helper("AI research methodology")
            
            captured = capsys.readouterr()
            
            # Expected behavior: successful research report display
            assert "# Research helper results" in captured.out, "Should display research report header"
            assert "AI research methodology" in captured.out, "Should display the query"
            assert "Valid Test Paper" in captured.out, "Should display paper titles"
            assert "Another Valid Paper" in captured.out, "Should display all papers"
            assert "Introduces novel AI methodology" in captured.out, "Should display key points"
            assert "Directly addresses the research query" in captured.out, "Should display relevance"
            
            # Should NOT contain error messages
            assert "❌ Error:" not in captured.out, "Should not display error messages for valid JSON"
            assert "-- RAW RESPONSE FROM LLM --" not in captured.out, "Should not show raw response for successful parsing"

    @pytest.mark.asyncio
    async def test_code_block_extraction_preservation(self, mock_successful_search, capsys):
        """Test that JSON wrapped in code blocks continues to be extracted correctly.
        
        **Property 2: Preservation** - Valid JSON Response Processing  
        **Validates: Requirements 3.2**
        
        EXPECTED ON UNFIXED CODE: Test PASSES (successful code block extraction and parsing)
        EXPECTED ON FIXED CODE: Test PASSES (same extraction behavior preserved)
        """
        # Test various code block formats that should continue working
        code_block_formats = [
            # Standard markdown code block with json language
            '''```json
{
    "query": "test query",
    "papers": [{"title": "Test Paper", "key_points": ["point"], "why_relevant": ["relevant"]}]
}```''',
            
            # Code block without language specification
            '''```
{
    "query": "test query", 
    "papers": [{"title": "Test Paper", "key_points": ["point"], "why_relevant": ["relevant"]}]
}```''',
            
            # Mixed content with JSON in code block
            '''Here is the analysis:

```json
{
    "query": "test query",
    "papers": [{"title": "Test Paper", "key_points": ["point"], "why_relevant": ["relevant"]}]
}```

This completes the analysis.'''
        ]

        for i, response_format in enumerate(code_block_formats):
            mock_result = MagicMock()
            mock_result.output = response_format

            with patch('src.retrieval.orchestrator.analysis_agent') as mock_agent:
                mock_agent.run = AsyncMock(return_value=mock_result)
                
                # Clear previous output
                capsys.readouterr()
                
                # This should extract and parse JSON successfully
                await run_research_helper(f"test query {i}")
                
                captured = capsys.readouterr()
                
                if i == 2:  # Mixed content case - now works with enhanced extraction
                    # Expected behavior: enhanced extraction now handles mixed content successfully
                    assert "# Research helper results" in captured.out, f"Enhanced extraction should handle mixed content for format {i}"
                    assert "test query" in captured.out, f"Should display query from mixed content format {i}"
                    assert "Test Paper" in captured.out, f"Should display paper from mixed content format {i}"
                    
                    # Should NOT contain error messages with enhanced extraction
                    assert "❌ Error:" not in captured.out, f"Enhanced extraction should not error on mixed content format {i}"
                else:
                    # Expected behavior: successful JSON extraction and parsing
                    assert "# Research helper results" in captured.out, f"Should extract JSON from code block format {i}"
                    assert "test query" in captured.out, f"Should display query from extracted JSON {i}"
                    assert "Test Paper" in captured.out, f"Should display paper from extracted JSON {i}"
                    
                    # Should NOT contain error messages
                    assert "❌ Error:" not in captured.out, f"Should not error on valid code block format {i}"

    @pytest.mark.asyncio
    async def test_network_error_handling_preservation(self, capsys):
        """Test that network error handling continues to work correctly.
        
        **Property 2: Preservation** - Valid JSON Response Processing
        **Validates: Requirements 3.3**
        
        EXPECTED ON UNFIXED CODE: Test PASSES (proper network error display)
        EXPECTED ON FIXED CODE: Test PASSES (same network error handling preserved)
        """
        # Mock network error during paper retrieval
        async def mock_network_error(*args, **kwargs):
            raise Exception("Connection timeout")
            
        with patch('src.retrieval.orchestrator.search_openalex', side_effect=mock_network_error), \
             patch('src.retrieval.orchestrator.search_semantic_scholar', side_effect=mock_network_error):
            
            # This should handle network error gracefully
            await run_research_helper("test query")
            
            captured = capsys.readouterr()
            
            # Expected behavior: network error message display
            expected_error = MessageFormatter.network_error("Connection timeout")
            assert expected_error in captured.out, "Should display network error message"
            assert "Check your internet connection" in captured.out, "Should provide helpful guidance"
            
            # Should NOT attempt JSON parsing or show parsing errors
            assert "❌ Error: Parsing Error:" not in captured.out, "Should not show JSON parsing errors for network issues"
            assert "-- RAW RESPONSE FROM LLM --" not in captured.out, "Should not show raw LLM response for network errors"

    @pytest.mark.asyncio
    async def test_no_results_handling_preservation(self, capsys):
        """Test that no-results scenarios continue to work correctly.
        
        **Property 2: Preservation** - Valid JSON Response Processing
        **Validates: Requirements 3.4**
        
        EXPECTED ON UNFIXED CODE: Test PASSES (proper no-results message display)
        EXPECTED ON FIXED CODE: Test PASSES (same no-results handling preserved)
        """
        # Mock empty search results
        async def mock_empty_results(*args, **kwargs):
            return []
            
        with patch('src.retrieval.orchestrator.search_openalex', side_effect=mock_empty_results), \
             patch('src.retrieval.orchestrator.search_semantic_scholar', side_effect=mock_empty_results):
            
            # This should handle no results gracefully
            await run_research_helper("obscure query with no results")
            
            captured = capsys.readouterr()
            
            # Expected behavior: no results message display
            expected_message = MessageFormatter.no_results_message()
            assert expected_message in captured.out, "Should display no results message"
            assert "No papers found. Try a different query." in captured.out, "Should provide helpful guidance"
            
            # Should NOT attempt JSON parsing or show parsing errors
            assert "❌ Error: Parsing Error:" not in captured.out, "Should not show JSON parsing errors for no results"
            assert "-- RAW RESPONSE FROM LLM --" not in captured.out, "Should not show raw LLM response for no results"


# Property-based tests for stronger preservation guarantees
class TestPreservationProperties:
    """Additional tests that verify preservation across multiple valid JSON patterns."""

    @pytest.fixture
    def mock_papers(self):
        """Mock papers for property testing."""
        return [
            RetrievedPaper(
                title="Property Test Paper",
                abstract="Abstract for property testing",
                year=2023,
                venue="Property Conference",
                url="https://example.com/property-paper",
                doi="10.1000/property-test",
                source="test"
            )
        ]

    @pytest.fixture
    def mock_successful_search(self, mock_papers):
        """Mock successful paper search for property testing."""
        async def mock_openalex(*args, **kwargs):
            return mock_papers
        
        async def mock_s2(*args, **kwargs):
            return []
            
        with patch('src.retrieval.orchestrator.search_openalex', side_effect=mock_openalex), \
             patch('src.retrieval.orchestrator.search_semantic_scholar', side_effect=mock_s2):
            yield

    @pytest.mark.asyncio
    @pytest.mark.parametrize("valid_json_data", [
        # Minimal valid structure
        {
            "query": "minimal test",
            "papers": []
        },
        # Single paper with all fields
        {
            "query": "single paper test",
            "papers": [{
                "title": "Complete Paper",
                "year": 2023,
                "venue": "Test Venue",
                "url": "https://example.com/paper",
                "doi": "10.1000/test",
                "key_points": ["point 1", "point 2"],
                "why_relevant": ["reason 1", "reason 2"]
            }]
        },
        # Multiple papers with optional fields
        {
            "query": "multiple papers test",
            "papers": [
                {
                    "title": "Paper 1",
                    "key_points": ["key point"],
                    "why_relevant": ["relevant because"]
                },
                {
                    "title": "Paper 2", 
                    "year": 2022,
                    "venue": "Another Venue",
                    "key_points": [],
                    "why_relevant": ["another reason"]
                }
            ]
        },
        # Papers with None values for optional fields
        {
            "query": "none values test",
            "papers": [{
                "title": "Paper with Nones",
                "year": None,
                "venue": None,
                "url": None,
                "doi": None,
                "key_points": ["some point"],
                "why_relevant": ["some reason"]
            }]
        }
    ])
    async def test_valid_json_structures_preservation_property(self, mock_successful_search, valid_json_data, capsys):
        """Test that various valid JSON structures continue to be processed correctly.
        
        **Property 2: Preservation** - Valid JSON Response Processing
        **Validates: Requirements 3.1, 3.2**
        
        This test covers multiple valid JSON structures to ensure the fix doesn't break
        any valid input patterns that currently work.
        
        EXPECTED ON UNFIXED CODE: Test PASSES (all valid JSON processed successfully)
        EXPECTED ON FIXED CODE: Test PASSES (same processing behavior preserved)
        """
        # Convert to JSON string with code block wrapping (common LLM format)
        json_string = json.dumps(valid_json_data, ensure_ascii=False, indent=2)
        response_with_code_block = f"```json\n{json_string}\n```"

        mock_result = MagicMock()
        mock_result.output = response_with_code_block

        with patch('src.retrieval.orchestrator.analysis_agent') as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            
            # This should process successfully without errors
            try:
                await run_research_helper("property test query")
                processing_successful = True
            except Exception as e:
                processing_successful = False
                pytest.fail(f"Valid JSON structure failed to process: {e}\nJSON: {json_string}")
            
            assert processing_successful, "All valid JSON structures should process successfully"
            
            captured = capsys.readouterr()
            
            # Should either show successful report or handle empty results gracefully
            if valid_json_data['papers']:  # If there are papers, should show report
                assert "# Research helper results" in captured.out, "Should display research report for valid JSON with papers"
                assert valid_json_data['query'] in captured.out, "Should display the query from valid JSON"
            else:  # If no papers, should handle gracefully (not an error)
                # Empty papers list is valid JSON but may result in empty report
                assert "❌ Error: Parsing Error:" not in captured.out, "Should not show parsing errors for valid JSON"
            
            # Should NEVER show raw response for valid JSON
            assert "-- RAW RESPONSE FROM LLM --" not in captured.out, "Should not show raw response for successful parsing"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("code_block_wrapper,should_work", [
        ("```json\n{content}\n```", True),
        ("```\n{content}\n```", True), 
        ("{content}", True),  # No wrapper
        ("Here's the analysis:\n```json\n{content}\n```\nEnd of analysis.", True),  # Mixed content - now works with enhanced extraction
    ])
    async def test_code_block_format_preservation_property(self, mock_successful_search, code_block_wrapper, should_work, capsys):
        """Test for different code block formats that should continue working.
        
        **Property 2: Preservation** - Valid JSON Response Processing
        **Validates: Requirements 3.2**
        
        EXPECTED ON UNFIXED CODE: Test PASSES (all formats extracted correctly)
        EXPECTED ON FIXED CODE: Test PASSES (same extraction behavior preserved)
        """
        # Valid JSON content
        json_content = json.dumps({
            "query": "format preservation test",
            "papers": [{
                "title": "Format Test Paper",
                "key_points": ["format testing"],
                "why_relevant": ["tests format preservation"]
            }]
        })
        
        # Apply the wrapper format
        formatted_response = code_block_wrapper.format(content=json_content)

        mock_result = MagicMock()
        mock_result.output = formatted_response

        with patch('src.retrieval.orchestrator.analysis_agent') as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            
            # This should extract and process successfully
            await run_research_helper("format preservation test")
            
            captured = capsys.readouterr()
            
            if should_work:
                # Expected behavior: successful extraction and processing
                assert "# Research helper results" in captured.out, f"Should extract JSON from format: {code_block_wrapper}"
                assert "format preservation test" in captured.out, f"Should display query from format: {code_block_wrapper}"
                assert "Format Test Paper" in captured.out, f"Should display paper from format: {code_block_wrapper}"
                
                # Should NOT show errors for valid JSON in supported formats
                assert "❌ Error: Parsing Error:" not in captured.out, f"Should not error on valid format: {code_block_wrapper}"
                assert "-- RAW RESPONSE FROM LLM --" not in captured.out, f"Should not show raw response for valid format: {code_block_wrapper}"
            else:
                # Expected behavior: graceful error handling for unsupported formats
                assert "❌ Error: Parsing Error:" in captured.out, f"Should show error for unsupported format: {code_block_wrapper}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("json_with_newlines,description", [
        ('{"query": "test", "papers": [{"title": "Multi-line\nTitle Paper"}]}', "literal newlines in string values"),
        ('{"query": "test", "papers": [{"title": "Paper with\n    indented continuation"}]}', "newlines with indentation in strings"),
        ('{"query": "test\nquery", "papers": [{"title": "Paper"}]}', "newlines in query field"),
    ])
    async def test_newline_handling_preservation_property(self, mock_successful_search, json_with_newlines, description, capsys):
        """Test that JSON with literal newlines in string values is now handled correctly.
        
        **Property 2: Preservation** - Enhanced JSON Processing with Newline Handling
        **Validates: The fix for literal newlines in JSON strings**
        
        This test ensures that our fix for handling literal newlines within JSON string values
        continues to work correctly. These cases previously caused "Invalid control character" 
        errors but should now be processed successfully.
        
        EXPECTED BEHAVIOR: Successful parsing and processing (no errors)
        """
        mock_result = MagicMock()
        mock_result.output = json_with_newlines

        with patch('src.retrieval.orchestrator.analysis_agent') as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)
            
            # This should now work successfully (no crashes or errors)
            await run_research_helper("newline test")
            
            captured = capsys.readouterr()
            
            # Expected behavior: successful processing without errors
            assert "# Research helper results" in captured.out, f"Should process JSON with {description}"
            assert "❌ Error: Parsing Error:" not in captured.out, f"Should not error on {description}"
            assert "-- RAW RESPONSE FROM LLM --" not in captured.out, f"Should not show raw response for {description}"
            
            # Should contain the processed content (with newlines removed from titles)
            if "Multi-line" in json_with_newlines:
                assert "Multi-lineTitle Paper" in captured.out, "Should join multi-line title"
            elif "indented continuation" in json_with_newlines:
                assert "Paper withindented continuation" in captured.out, "Should join indented continuation"