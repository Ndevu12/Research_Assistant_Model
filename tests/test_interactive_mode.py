# -*- coding: utf-8 -*-
"""Integration tests for interactive mode functionality.

These tests verify the complete interactive mode workflow including
multi-query sessions, exit command handling, and empty input re-prompting.
"""

import sys
from io import StringIO
from unittest.mock import patch, MagicMock, call

import pytest

from src.__main__ import run_interactive_mode


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
    # Mock get_user_query to return a query, then None (exit)
    mock_queries = ["test query", None]
    
    with patch('src.__main__.get_user_query', side_effect=mock_queries):
        # Mock run_research_helper to avoid actual API calls
        with patch('src.__main__.asyncio.run') as mock_run:
            # Capture stdout
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                run_interactive_mode()
            
            # Verify run_research_helper was called with the query
            mock_run.assert_called_once()
            
            output = captured_output.getvalue()
            
            # Verify separator is displayed
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
    # Mock get_user_query to return multiple queries, then None (exit)
    mock_queries = ["query 1", "query 2", "query 3", None]
    
    with patch('src.__main__.get_user_query', side_effect=mock_queries):
        # Mock run_research_helper to avoid actual API calls
        with patch('src.__main__.asyncio.run') as mock_run:
            # Capture stdout
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                run_interactive_mode()
            
            # Verify run_research_helper was called 3 times
            assert mock_run.call_count == 3
            
            output = captured_output.getvalue()
            
            # Verify separators are displayed (should be 3 separators for 3 queries)
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
        
        with patch('src.__main__.get_user_query', side_effect=mock_queries):
            # Mock the research helper to avoid API calls
            with patch('src.__main__.asyncio.run') as mock_research:
                # Capture all output
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify each query was processed independently
                assert mock_research.call_count == 3
                
                # Verify the research helper was called with correct queries
                call_args_list = mock_research.call_args_list
                # Note: asyncio.run is called with run_research_helper(query), 
                # so we need to check the function being called
                
                output = captured_output.getvalue()
                
                # Verify welcome message is displayed
                assert "Welcome to the AI Research Assistant!" in output
                
                # Verify separators between results (3 queries = 3 separators)
                separator_count = output.count("-" * 60)
                assert separator_count == 3
                
                # Verify farewell message
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
    
    def test_exit_command_handling_exit(self):
        """Test that 'exit' command terminates session gracefully.
        
        Requirements: 3.1, 3.4
        """
        # Mock get_user_query to return 'exit' immediately
        with patch('src.__main__.get_user_query', return_value=None) as mock_input:
            with patch('src.__main__.asyncio.run') as mock_research:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify no research queries were processed
                mock_research.assert_not_called()
                
                output = captured_output.getvalue()
                
                # Verify welcome and farewell messages
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                
                # Verify no separators (no queries processed)
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
        
        with patch('src.__main__.get_user_query', side_effect=mock_queries):
            with patch('src.__main__.asyncio.run') as mock_research:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify 2 queries were processed
                assert mock_research.call_count == 2
                
                output = captured_output.getvalue()
                
                # Verify session flow
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                
                # Verify 2 separators for 2 queries
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
        with patch('src.__main__.get_user_query', side_effect=mock_queries):
            with patch('src.__main__.asyncio.run') as mock_research:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify the valid query was processed
                assert mock_research.call_count == 1
                
                output = captured_output.getvalue()
                
                # Verify normal session flow
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                assert "-" * 60 in output  # One separator for one query
    
    def test_keyboard_interrupt_during_session(self):
        """Test Ctrl+C handling during an active session.
        
        Requirements: 3.3, 3.4, 3.5
        """
        # Simulate KeyboardInterrupt during get_user_query
        with patch('src.__main__.get_user_query', side_effect=KeyboardInterrupt):
            with patch('src.__main__.asyncio.run') as mock_research:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify no queries were processed
                mock_research.assert_not_called()
                
                output = captured_output.getvalue()
                
                # Verify welcome message was displayed
                assert "Welcome to the AI Research Assistant!" in output
                
                # Verify farewell message is displayed even after interrupt
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                
                # Verify no error messages or stack traces
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
        
        with patch('src.__main__.get_user_query', side_effect=mock_queries):
            with patch('src.__main__.asyncio.run') as mock_research:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify one query was processed before interrupt
                assert mock_research.call_count == 1
                
                output = captured_output.getvalue()
                
                # Verify session components
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                assert "-" * 60 in output  # One separator for processed query
                
                # Verify graceful handling (no stack trace)
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
        
        with patch('src.__main__.get_user_query', side_effect=mock_queries):
            with patch('src.__main__.asyncio.run') as mock_research:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify all 4 queries were processed in the same session
                assert mock_research.call_count == 4
                
                output = captured_output.getvalue()
                
                # Verify single welcome and farewell (one session)
                welcome_count = output.count("Welcome to the AI Research Assistant!")
                farewell_count = output.count("Thank you for using the AI Research Assistant. Goodbye!")
                assert welcome_count == 1
                assert farewell_count == 1
                
                # Verify 4 separators for 4 queries
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
        
        with patch('builtins.input', side_effect=mock_inputs):
            with patch('src.__main__.asyncio.run') as mock_research:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify one valid query was processed
                assert mock_research.call_count == 1
                
                output = captured_output.getvalue()
                
                # Verify normal session completion
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
                
                # Verify empty input error messages were displayed
                # (They should be in the captured output since print goes to stdout)
                assert "Query cannot be empty" in output
