# -*- coding: utf-8 -*-
"""Integration tests for interactive mode functionality.

These tests verify the complete interactive mode workflow including
multi-query sessions, exit command handling, and empty input re-prompting.
"""

import sys
from contextlib import contextmanager
from io import StringIO
from unittest.mock import AsyncMock, patch, MagicMock, call

import pytest

from src.__main__ import run_interactive_mode


@contextmanager
def _mock_session_async(research_output: str = "mock report"):
    """Mock interactive session async helpers while keeping real asyncio.run."""
    with patch("src.__main__._initialize_session", new=AsyncMock()) as init_mock:
        with patch("src.__main__._handle_follow_up", new=AsyncMock(return_value=None)) as follow_mock:
            with patch(
                "src.__main__._run_session_query",
                new=AsyncMock(return_value=research_output),
            ) as query_mock:
                yield init_mock, follow_mock, query_mock


def test_run_interactive_mode_displays_welcome_message():
    """Test that interactive mode displays welcome message."""
    # Mock get_user_query to return None (exit immediately)
    with patch('src.__main__.get_user_query', return_value=None):
        # Capture stdout
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            run_interactive_mode()
        
        output = captured_output.getvalue()
        
        # Verify welcome message components
        assert "Welcome to the AI Research Assistant!" in output
        assert "How to use:" in output
        assert "Enter your research query when prompted" in output
        assert "Type 'exit' or 'quit' to end your session" in output
        assert "Press Ctrl+C to exit at any time" in output


def test_run_interactive_mode_displays_farewell_message():
    """Test that interactive mode displays farewell message on exit."""
    # Mock get_user_query to return None (exit immediately)
    with patch('src.__main__.get_user_query', return_value=None):
        # Capture stdout
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            run_interactive_mode()
        
        output = captured_output.getvalue()
        
        # Verify farewell message
        assert "Thank you for using the AI Research Assistant. Goodbye!" in output


def test_run_interactive_mode_processes_query_and_continues():
    """Test that interactive mode processes a query and prompts for another."""
    mock_queries = ["test query", None]

    with patch("src.__main__.get_user_query", side_effect=mock_queries):
        with _mock_session_async() as (_, _, query_mock):
            captured_output = StringIO()
            with patch("sys.stdout", captured_output):
                run_interactive_mode()

            query_mock.assert_called_once()
            output = captured_output.getvalue()
            assert "-" * 60 in output


def test_run_interactive_mode_handles_keyboard_interrupt():
    """Test that interactive mode handles Ctrl+C gracefully."""
    # Mock get_user_query to raise KeyboardInterrupt
    with patch('src.__main__.get_user_query', side_effect=KeyboardInterrupt):
        # Capture stdout
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            run_interactive_mode()
        
        output = captured_output.getvalue()
        
        # Verify farewell message is still displayed
        assert "Thank you for using the AI Research Assistant. Goodbye!" in output
        
        # Verify no error or stack trace
        assert "Traceback" not in output
        assert "Error" not in output or "Error fetching papers" in output  # Allow API errors


def test_run_interactive_mode_processes_multiple_queries():
    """Test that interactive mode can process multiple queries in sequence."""
    mock_queries = ["query 1", "query 2", "query 3", None]

    with patch("src.__main__.get_user_query", side_effect=mock_queries):
        with _mock_session_async() as (_, _, query_mock):
            captured_output = StringIO()
            with patch("sys.stdout", captured_output):
                run_interactive_mode()

            assert query_mock.call_count == 3
            output = captured_output.getvalue()
            assert output.count("-" * 60) == 3


class TestInteractiveModeIntegration:
    """Integration tests for interactive mode covering complete workflows."""
    
    def test_multi_query_session_flow(self):
        """Test complete multi-query session flow with processing and separators.
        
        Requirements: 2.1, 2.2, 2.3, 2.4
        """
        # Simulate a session with multiple queries
        mock_queries = [
            "machine learning research",
            "neural networks",
            "deep learning applications", 
            None  # Exit
        ]
        
        with patch("src.__main__.get_user_query", side_effect=mock_queries):
            with _mock_session_async() as (_, _, query_mock):
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    run_interactive_mode()

                assert query_mock.call_count == 3

                output = captured_output.getvalue()
                assert "Welcome to the AI Research Assistant!" in output
                assert output.count("-" * 60) == 3
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
    
    def test_exit_command_handling_exit(self):
        """Test that 'exit' command terminates session gracefully.
        
        Requirements: 3.1, 3.4
        """
        # Mock get_user_query to return 'exit' immediately
        with patch("src.__main__.get_user_query", return_value=None):
            with _mock_session_async() as (_, _, query_mock):
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    run_interactive_mode()

                query_mock.assert_not_called()

                output = captured_output.getvalue()
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                assert "-" * 60 not in output
    
    def test_exit_command_handling_after_queries(self):
        """Test exit command after processing some queries.
        
        Requirements: 3.1, 3.4, 2.1, 2.2
        """
        # Process some queries then exit
        mock_queries = [
            "first query",
            "second query", 
            None  # Exit
        ]
        
        with patch("src.__main__.get_user_query", side_effect=mock_queries):
            with _mock_session_async() as (_, _, query_mock):
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    run_interactive_mode()

                assert query_mock.call_count == 2

                output = captured_output.getvalue()
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                assert output.count("-" * 60) == 2
    
    def test_empty_input_re_prompting_integration(self):
        """Test empty input handling integrated with query processing.
        
        Requirements: 4.1, 4.2, 4.3
        """
        # Simulate empty inputs followed by valid query and exit
        # Note: get_user_query handles empty input internally and re-prompts,
        # so we simulate the final result after re-prompting
        mock_queries = [
            "valid query after empty inputs",
            None  # Exit
        ]
        
        # Mock get_user_query to simulate internal empty input handling
        with patch("src.__main__.get_user_query", side_effect=mock_queries):
            with _mock_session_async() as (_, _, query_mock):
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    run_interactive_mode()

                assert query_mock.call_count == 1

                output = captured_output.getvalue()
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                assert "-" * 60 in output
    
    def test_keyboard_interrupt_during_session(self):
        """Test Ctrl+C handling during an active session.
        
        Requirements: 3.3, 3.4, 3.5
        """
        # Simulate KeyboardInterrupt during get_user_query
        with patch("src.__main__.get_user_query", side_effect=KeyboardInterrupt):
            with _mock_session_async() as (_, _, query_mock):
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    run_interactive_mode()

                query_mock.assert_not_called()

                output = captured_output.getvalue()
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                assert "Traceback" not in output
                assert "Error" not in output or "Error fetching papers" in output
    
    def test_keyboard_interrupt_after_processing_queries(self):
        """Test Ctrl+C handling after processing some queries.
        
        Requirements: 3.3, 3.4, 3.5, 2.1, 2.2
        """
        # Process one query, then interrupt
        mock_queries = [
            "processed query",
            KeyboardInterrupt()  # Interrupt on second prompt
        ]
        
        with patch("src.__main__.get_user_query", side_effect=mock_queries):
            with _mock_session_async() as (_, _, query_mock):
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    run_interactive_mode()

                assert query_mock.call_count == 1

                output = captured_output.getvalue()
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                assert "-" * 60 in output
                assert "Traceback" not in output
    
    def test_session_maintains_state_across_queries(self):
        """Test that session state is maintained across multiple queries.
        
        Requirements: 2.3 (maintain session until explicit exit)
        """
        # Multiple queries to verify session persistence
        mock_queries = [
            "query one",
            "query two", 
            "query three",
            "query four",
            None  # Exit
        ]
        
        with patch("src.__main__.get_user_query", side_effect=mock_queries):
            with _mock_session_async() as (_, _, query_mock):
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    run_interactive_mode()

                assert query_mock.call_count == 4

                output = captured_output.getvalue()
                assert output.count("Welcome to the AI Research Assistant!") == 1
                assert output.count("Thank you for using the AI Research Assistant. Goodbye!") == 1
                assert output.count("-" * 60) == 4
    
    def test_integration_with_input_handler_empty_input_flow(self):
        """Test integration between interactive mode and input handler for empty input.
        
        This test verifies the complete flow when empty input is encountered,
        including the re-prompting behavior from input_handler.
        
        Requirements: 4.1, 4.2, 4.3
        """
        # We'll mock the input function directly to simulate the complete flow
        # including empty input handling within get_user_query
        mock_inputs = [
            "",  # Empty input (should trigger error and re-prompt)
            "   ",  # Whitespace-only (should trigger error and re-prompt) 
            "valid research query",  # Valid input
            "exit"  # Exit command
        ]
        
        with patch("builtins.input", side_effect=mock_inputs):
            with _mock_session_async() as (_, _, query_mock):
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    run_interactive_mode()

                assert query_mock.call_count == 1

                output = captured_output.getvalue()
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                assert "Query cannot be empty" in output
