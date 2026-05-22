# -*- coding: utf-8 -*-
"""Tests for signal handling in interactive mode.

These tests verify that KeyboardInterrupt (Ctrl+C) is handled gracefully
without displaying error messages or stack traces, and that the farewell
message is always displayed on exit.

Requirements tested:
- 3.3: KeyboardInterrupt handling
- 3.5: No error messages or stack traces on normal exit
"""

import sys
import signal
import os
import subprocess
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest

from src.__main__ import run_interactive_mode


class TestSignalHandling:
    """Test signal handling in interactive mode."""
    
    def test_keyboard_interrupt_displays_farewell_message(self):
        """Test that KeyboardInterrupt displays farewell message without errors.
        
        Requirements: 3.3, 3.4, 3.5
        """
        # Mock get_user_query to raise KeyboardInterrupt immediately
        with patch('src.__main__.get_user_query', side_effect=KeyboardInterrupt):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                # Should not raise exception
                run_interactive_mode()
            
            output = captured_output.getvalue()
            
            # Verify farewell message is displayed
            assert "Thank you for using the AI Research Assistant. Goodbye!" in output
            
            # Verify no error messages or stack traces
            assert "Traceback" not in output
            assert "Exception" not in output
            assert "KeyboardInterrupt" not in output
            assert "Error:" not in output or "Error fetching papers" in output  # Allow API errors
    
    def test_keyboard_interrupt_after_welcome_message(self):
        """Test KeyboardInterrupt after welcome message is displayed.
        
        Requirements: 3.3, 3.5
        """
        with patch('src.__main__.get_user_query', side_effect=KeyboardInterrupt):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                run_interactive_mode()
            
            output = captured_output.getvalue()
            
            # Verify both welcome and farewell messages
            assert "Welcome to the AI Research Assistant!" in output
            assert "Thank you for using the AI Research Assistant. Goodbye!" in output
            
            # Verify clean output (no stack traces)
            lines = output.split('\n')
            error_lines = [line for line in lines if 'Traceback' in line or 'Exception' in line]
            assert len(error_lines) == 0
    
    def test_keyboard_interrupt_during_query_processing(self):
        """Test KeyboardInterrupt during query processing loop.
        
        Requirements: 3.3, 3.5
        """
        # First call returns a query, second call raises KeyboardInterrupt
        mock_calls = ["test query", KeyboardInterrupt()]
        
        with patch('src.__main__.get_user_query', side_effect=mock_calls):
            # Mock asyncio.run to avoid actual processing
            with patch('src.__main__.asyncio.run') as mock_run:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify one query was processed before interrupt (1 init + 1 query)
                assert mock_run.call_count == 2
            
            output = captured_output.getvalue()
            
            # Verify farewell message despite interrupt
            assert "Thank you for using the AI Research Assistant. Goodbye!" in output
            
            # Verify no error output
            assert "Traceback" not in output
            assert "KeyboardInterrupt" not in output
    
    def test_keyboard_interrupt_graceful_exit_code(self):
        """Test that KeyboardInterrupt results in clean exit (no exception propagation).
        
        Requirements: 3.3, 3.5
        """
        with patch('src.__main__.get_user_query', side_effect=KeyboardInterrupt):
            captured_output = StringIO()
            captured_error = StringIO()
            
            with patch('sys.stdout', captured_output):
                with patch('sys.stderr', captured_error):
                    # This should complete without raising an exception
                    try:
                        run_interactive_mode()
                        exception_raised = False
                    except Exception:
                        exception_raised = True
                    
                    # Verify no exception was raised
                    assert not exception_raised
            
            # Verify no error output to stderr
            error_output = captured_error.getvalue()
            assert error_output == ""
            
            # Verify stdout has clean output
            stdout_output = captured_output.getvalue()
            assert "Thank you for using the AI Research Assistant. Goodbye!" in stdout_output
    
    def test_multiple_keyboard_interrupts_handled_gracefully(self):
        """Test that multiple KeyboardInterrupts are handled without issues.
        
        Requirements: 3.3, 3.5
        """
        # Simulate multiple interrupts (though only first should matter)
        interrupts = [KeyboardInterrupt(), KeyboardInterrupt(), KeyboardInterrupt()]
        
        with patch('src.__main__.get_user_query', side_effect=interrupts):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                run_interactive_mode()
            
            output = captured_output.getvalue()
            
            # Should still display farewell message once
            farewell_count = output.count("Thank you for using the AI Research Assistant. Goodbye!")
            assert farewell_count == 1
            
            # No error traces
            assert "Traceback" not in output
    
    def test_keyboard_interrupt_preserves_output_formatting(self):
        """Test that KeyboardInterrupt doesn't break output formatting.
        
        Requirements: 3.3, 3.5
        """
        with patch('src.__main__.get_user_query', side_effect=KeyboardInterrupt):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                run_interactive_mode()
            
            output = captured_output.getvalue()
            
            # Verify proper formatting is maintained
            assert "Welcome to the AI Research Assistant!" in output
            assert "=" * 60 in output  # Welcome message separator
            assert "Thank you for using the AI Research Assistant. Goodbye!" in output
            
            # Verify newline after ^C is present (from print() in except block)
            lines = output.split('\n')
            # Should have welcome section, then farewell
            assert len([line for line in lines if line.strip()]) >= 2
    
    def test_signal_handling_finally_block_execution(self):
        """Test that finally block always executes to display farewell message.
        
        Requirements: 3.4, 3.5
        """
        # Test various exception scenarios to ensure finally block runs
        test_exceptions = [
            KeyboardInterrupt(),
            KeyboardInterrupt(),  # Test multiple times
        ]
        
        for exception in test_exceptions:
            with patch('src.__main__.get_user_query', side_effect=exception):
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                output = captured_output.getvalue()
                
                # Finally block should always execute
                assert "Thank you for using the AI Research Assistant. Goodbye!" in output
    
    def test_normal_exit_vs_interrupt_exit_same_behavior(self):
        """Test that normal exit and interrupt exit produce similar clean output.
        
        Requirements: 3.5
        """
        # Test normal exit
        with patch('src.__main__.get_user_query', return_value=None):
            normal_output = StringIO()
            with patch('sys.stdout', normal_output):
                run_interactive_mode()
        
        # Test interrupt exit
        with patch('src.__main__.get_user_query', side_effect=KeyboardInterrupt):
            interrupt_output = StringIO()
            with patch('sys.stdout', interrupt_output):
                run_interactive_mode()
        
        normal_text = normal_output.getvalue()
        interrupt_text = interrupt_output.getvalue()
        
        # Both should have farewell message
        assert "Thank you for using the AI Research Assistant. Goodbye!" in normal_text
        assert "Thank you for using the AI Research Assistant. Goodbye!" in interrupt_text
        
        # Both should have welcome message
        assert "Welcome to the AI Research Assistant!" in normal_text
        assert "Welcome to the AI Research Assistant!" in interrupt_text
        
        # Neither should have error traces
        assert "Traceback" not in normal_text
        assert "Traceback" not in interrupt_text
        
        # Interrupt output might have one extra newline (from print() after ^C)
        # but otherwise should be very similar in structure
        normal_lines = [line for line in normal_text.split('\n') if line.strip()]
        interrupt_lines = [line for line in interrupt_text.split('\n') if line.strip()]
        
        # Should have same key components
        assert len(normal_lines) >= 3  # Welcome header, instructions, farewell
        assert len(interrupt_lines) >= 3  # Same components


class TestSignalHandlingIntegration:
    """Integration tests for signal handling with other components."""
    
    def test_keyboard_interrupt_with_input_handler_integration(self):
        """Test KeyboardInterrupt integration with input handler.
        
        Requirements: 3.3, 3.5
        """
        # Test interrupt at different points in the input handling flow
        with patch('builtins.input', side_effect=KeyboardInterrupt):
            # This tests the case where KeyboardInterrupt happens during input()
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                # get_user_query should propagate KeyboardInterrupt to run_interactive_mode
                run_interactive_mode()
            
            output = captured_output.getvalue()
            
            # Should still handle gracefully
            assert "Thank you for using the AI Research Assistant. Goodbye!" in output
            assert "Traceback" not in output
    
    def test_keyboard_interrupt_with_message_formatter_integration(self):
        """Test that KeyboardInterrupt doesn't interfere with message formatting.
        
        Requirements: 3.3, 3.5
        """
        with patch('src.__main__.get_user_query', side_effect=KeyboardInterrupt):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                run_interactive_mode()
            
            output = captured_output.getvalue()
            
            # Verify MessageFormatter methods work correctly
            from src.utils.message_formatter import MessageFormatter
            
            expected_welcome = MessageFormatter.welcome_message()
            expected_farewell = MessageFormatter.farewell_message()
            
            # Key parts should be present
            assert "Welcome to the AI Research Assistant!" in output
            assert "Thank you for using the AI Research Assistant. Goodbye!" in output
            assert "=" * 60 in output  # Welcome separator
    
    def test_signal_handling_preserves_session_state(self):
        """Test that signal handling doesn't corrupt session state.
        
        Requirements: 3.3, 3.5
        """
        # Process one query successfully, then interrupt
        mock_calls = ["successful query", KeyboardInterrupt()]
        
        with patch('src.__main__.get_user_query', side_effect=mock_calls):
            with patch('src.__main__.asyncio.run') as mock_run:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    run_interactive_mode()
                
                # Verify the successful query was processed (1 init + 1 query)
                assert mock_run.call_count == 2
            
            output = captured_output.getvalue()
            
            # Verify complete session flow
            assert "Welcome to the AI Research Assistant!" in output
            assert "-" * 60 in output  # Result separator from successful query
            assert "Thank you for using the AI Research Assistant. Goodbye!" in output
            
            # No corruption or errors
            assert "Traceback" not in output