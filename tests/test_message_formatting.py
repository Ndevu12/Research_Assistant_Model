# -*- coding: utf-8 -*-
"""Tests for message formatting consistency (Tasks 6.1 and 6.2)."""

from io import StringIO
from unittest.mock import patch

from src.__main__ import run_interactive_mode
from src.utils.input_handler import get_user_query
from src.utils.message_formatter import MessageFormatter


def test_clear_input_indicator():
    """Test that the input prompt displays a clear indicator (Task 6.2, Req 5.4)."""
    # Mock input to return a query immediately
    with patch('builtins.input', return_value='test query'):
        query = get_user_query()
        assert query == 'test query'
    
    # Verify the prompt text is consistent
    expected_prompt = MessageFormatter.query_prompt()
    assert expected_prompt == "Enter your research query (or 'exit'/'quit' to quit): "


def test_error_message_formatting():
    """Test that error messages have clear formatting (Task 6.2, Req 5.4)."""
    # Mock input to return empty string, then a valid query
    with patch('builtins.input', side_effect=['', 'valid query']):
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            query = get_user_query()
        
        output = captured_output.getvalue()
        
        # Verify error message uses consistent formatting
        expected_error = MessageFormatter.empty_query_error()
        assert expected_error in output
        assert "❌ Error:" in output
        assert "Query cannot be empty" in output
        assert query == 'valid query'


def test_consistent_message_formatting():
    """Test that all interactive mode messages use consistent formatting (Task 6.1, Req 5.5)."""
    # Mock get_user_query to return None (exit immediately)
    with patch('src.__main__.get_user_query', return_value=None):
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            run_interactive_mode()
        
        output = captured_output.getvalue()
        
        # Verify consistent use of separators
        assert MessageFormatter.MAJOR_SEPARATOR in output  # Welcome separator
        
        # Verify consistent use of bullet points in instructions
        assert "  • Enter your research query when prompted" in output
        assert "  • Type 'exit' or 'quit' to end your session" in output
        assert "  • Press Ctrl+C to exit at any time" in output
        
        # Verify farewell message uses consistent formatting
        expected_farewell = MessageFormatter.farewell_message()
        assert expected_farewell in output


def test_result_separator_formatting():
    """Test that result separators are consistently formatted (Task 6.1, Req 5.5)."""
    # Mock get_user_query to return a query, then None (exit)
    mock_queries = ["test query", None]
    
    with patch('src.__main__.get_user_query', side_effect=mock_queries):
        # Mock run_research_helper to avoid actual API calls
        with patch('src.__main__.asyncio.run'):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                run_interactive_mode()
            
            output = captured_output.getvalue()
            
            # Verify separator uses consistent formatting
            expected_separator = MessageFormatter.result_separator()
            assert expected_separator in output
            assert MessageFormatter.MINOR_SEPARATOR in output


def test_message_formatter_utilities():
    """Test that MessageFormatter provides consistent formatting utilities (Task 6.1, Req 5.5)."""
    # Test separator constants
    assert MessageFormatter.MAJOR_SEPARATOR == "=" * 60
    assert MessageFormatter.MINOR_SEPARATOR == "-" * 60
    
    # Test error prefix consistency
    assert MessageFormatter.ERROR_PREFIX == "❌ Error:"
    
    # Test message methods return consistent formats
    welcome = MessageFormatter.welcome_message()
    assert MessageFormatter.MAJOR_SEPARATOR in welcome
    assert "Welcome to the AI Research Assistant!" in welcome
    
    farewell = MessageFormatter.farewell_message()
    assert "Thank you for using the AI Research Assistant. Goodbye!" in farewell
    
    error = MessageFormatter.error_message("test error")
    assert error.startswith("❌ Error:")
    assert "test error" in error
    
    empty_error = MessageFormatter.empty_query_error()
    assert "❌ Error:" in empty_error
    assert "Query cannot be empty" in empty_error
