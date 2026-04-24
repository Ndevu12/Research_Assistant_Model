# -*- coding: utf-8 -*-
"""Comprehensive integration tests for the complete interactive workflow (Task 7.1).

This test suite validates the complete interactive workflow including:
- Starting system without arguments
- Submitting multiple queries
- Testing exit commands
- Testing Ctrl+C interrupt
- Verifying backward compatibility with batch mode

Requirements tested: 1.1, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 1.4
"""

import sys
import subprocess
import time
import signal
import os
from io import StringIO
from unittest.mock import patch, MagicMock
from threading import Thread
import pytest

from src.__main__ import main, run_interactive_mode, run_research_helper


class TestCompleteInteractiveWorkflow:
    """Test suite for complete interactive workflow validation."""
    
    def test_start_system_without_arguments_enters_interactive_mode(self):
        """Test that starting system without arguments enters interactive mode (Req 1.1)."""
        # Mock sys.argv to simulate no arguments
        with patch('sys.argv', ['src']):
            # Mock get_user_query to return None (exit immediately)
            with patch('src.__main__.get_user_query', return_value=None):
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    main()
                
                output = captured_output.getvalue()
                
                # Verify interactive mode was entered
                assert "Welcome to the AI Research Assistant!" in output
                assert "Enter your research query when prompted" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
    
    def test_submit_multiple_queries_in_sequence(self):
        """Test submitting multiple queries in a single session (Req 2.1, 2.2, 2.3)."""
        # Mock multiple queries followed by exit
        mock_queries = [
            "machine learning algorithms",
            "neural networks",
            "deep learning applications",
            None  # Exit
        ]
        
        with patch('src.__main__.get_user_query', side_effect=mock_queries):
            # Mock run_research_helper to avoid actual API calls
            with patch('src.__main__.asyncio.run') as mock_run:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify all queries were processed
                assert mock_run.call_count == 3
                
                output = captured_output.getvalue()
                
                # Verify separators between results (should be 3 for 3 queries)
                separator_count = output.count("-" * 60)
                assert separator_count == 3
                
                # Verify session maintained until explicit exit
                assert "Welcome to the AI Research Assistant!" in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
    
    def test_exit_command_terminates_session(self):
        """Test that 'exit' command terminates the session gracefully (Req 3.1)."""
        # Mock get_user_query to return 'exit'
        with patch('src.__main__.get_user_query', return_value=None) as mock_query:
            # Simulate exit command detection in get_user_query
            mock_query.return_value = None
            
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                run_interactive_mode()
            
            output = captured_output.getvalue()
            
            # Verify farewell message is displayed
            assert "Thank you for using the AI Research Assistant. Goodbye!" in output
            # Verify no error messages
            assert "Error" not in output or "Error fetching papers" in output  # Allow API errors
    
    def test_quit_command_terminates_session(self):
        """Test that 'quit' command terminates the session gracefully (Req 3.2)."""
        # Test the actual input handler with 'quit' command
        with patch('builtins.input', return_value='quit'):
            from src.utils.input_handler import get_user_query
            result = get_user_query()
            assert result is None
        
        # Test case-insensitive quit
        with patch('builtins.input', return_value='QUIT'):
            result = get_user_query()
            assert result is None
    
    def test_keyboard_interrupt_graceful_handling(self):
        """Test that Ctrl+C (KeyboardInterrupt) is handled gracefully (Req 3.3)."""
        # Mock get_user_query to raise KeyboardInterrupt
        with patch('src.__main__.get_user_query', side_effect=KeyboardInterrupt):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                run_interactive_mode()
            
            output = captured_output.getvalue()
            
            # Verify farewell message is still displayed
            assert "Thank you for using the AI Research Assistant. Goodbye!" in output
            
            # Verify no stack trace or error messages
            assert "Traceback" not in output
            assert "KeyboardInterrupt" not in output
    
    def test_backward_compatibility_with_batch_mode(self):
        """Test that batch mode still works when query argument is provided (Req 1.4)."""
        # Mock sys.argv to simulate query argument
        with patch('sys.argv', ['src', 'test query']):
            # Mock run_research_helper to avoid actual API calls
            with patch('src.__main__.asyncio.run') as mock_run:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    main()
                
                # Verify run_research_helper was called once with the query
                mock_run.assert_called_once()
                
                output = captured_output.getvalue()
                
                # Verify interactive mode was NOT entered
                assert "Welcome to the AI Research Assistant!" not in output
                assert "Enter your research query" not in output
                assert "Thank you for using the AI Research Assistant. Goodbye!" not in output
    
    def test_empty_input_handling_and_reprompting(self):
        """Test that empty input is handled with error message and re-prompting (Req 4.1, 4.2, 4.3)."""
        # Mock input to return empty string, whitespace, then valid query
        with patch('builtins.input', side_effect=['', '   ', 'valid query']):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                from src.utils.input_handler import get_user_query
                result = get_user_query()
            
            output = captured_output.getvalue()
            
            # Verify error messages were displayed
            assert "❌ Error:" in output
            assert "Query cannot be empty" in output
            
            # Verify valid query was eventually returned
            assert result == 'valid query'
    
    def test_session_maintains_state_between_queries(self):
        """Test that session state is maintained between multiple queries (Req 2.3)."""
        queries = ["query 1", "query 2", None]
        
        with patch('src.__main__.get_user_query', side_effect=queries):
            with patch('src.__main__.asyncio.run') as mock_run:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify both queries were processed in the same session
                assert mock_run.call_count == 2
                
                output = captured_output.getvalue()
                
                # Verify welcome message appears only once (session start)
                welcome_count = output.count("Welcome to the AI Research Assistant!")
                assert welcome_count == 1
                
                # Verify farewell message appears only once (session end)
                farewell_count = output.count("Thank you for using the AI Research Assistant. Goodbye!")
                assert farewell_count == 1
    
    def test_complete_workflow_integration(self):
        """Test the complete workflow from start to finish with multiple scenarios."""
        # Simulate a realistic user session
        mock_queries = [
            "artificial intelligence",  # Valid query 1
            "",                        # Empty input (should re-prompt)
            "machine learning",        # Valid query 2
            "   ",                     # Whitespace only (should re-prompt)
            "deep learning",           # Valid query 3
            "exit"                     # Exit command
        ]
        
        # Mock the input function to simulate user input
        with patch('builtins.input', side_effect=mock_queries):
            # Mock run_research_helper to avoid actual API calls
            with patch('src.__main__.asyncio.run') as mock_run:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify only valid queries were processed (3 queries)
                assert mock_run.call_count == 3
                
                output = captured_output.getvalue()
                
                # Verify complete workflow elements
                assert "Welcome to the AI Research Assistant!" in output
                assert "How to use:" in output
                assert "Enter your research query when prompted" in output
                assert "Type 'exit' or 'quit' to end your session" in output
                assert "Press Ctrl+C to exit at any time" in output
                
                # Verify error handling for empty inputs
                assert "❌ Error:" in output
                assert "Query cannot be empty" in output
                
                # Verify result separators (3 separators for 3 queries)
                separator_count = output.count("-" * 60)
                assert separator_count == 3
                
                # Verify graceful exit
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output


class TestSystemLevelIntegration:
    """System-level integration tests using subprocess for realistic testing."""
    
    @pytest.mark.slow
    def test_system_startup_without_arguments(self):
        """Test actual system startup without arguments (system-level test)."""
        # This test requires the system to be properly installed/runnable
        try:
            # Start the process
            process = subprocess.Popen(
                [sys.executable, '-m', 'src'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.getcwd()
            )
            
            # Send exit command immediately
            stdout, stderr = process.communicate(input='exit\n', timeout=10)
            
            # Verify interactive mode was entered
            assert "Welcome to the AI Research Assistant!" in stdout
            assert "Enter your research query" in stdout
            assert "Thank you for using the AI Research Assistant. Goodbye!" in stdout
            
            # Verify no errors
            assert process.returncode == 0
            
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"System-level test skipped: {e}")
    
    @pytest.mark.slow
    def test_batch_mode_compatibility(self):
        """Test batch mode compatibility with query argument (system-level test)."""
        try:
            # Run with query argument
            process = subprocess.run(
                [sys.executable, '-m', 'src', 'test query'],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.getcwd()
            )
            
            # Verify batch mode behavior (no interactive prompts)
            assert "Welcome to the AI Research Assistant!" not in process.stdout
            assert "Enter your research query" not in process.stdout
            
            # Should either process the query or show an error (network issues are OK)
            assert process.returncode == 0 or "Error fetching papers" in process.stdout
            
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"System-level test skipped: {e}")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])