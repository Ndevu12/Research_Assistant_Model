# -*- coding: utf-8 -*-
"""Unit tests for input handler module.

Tests the get_user_query() function for various input scenarios including
empty input, whitespace-only input, exit commands, and valid queries.
"""

import pytest
from unittest.mock import patch, call
from src.utils.input_handler import get_user_query
from src.utils.message_formatter import MessageFormatter


class TestGetUserQuery:
    """Test cases for the get_user_query function."""
    
    def test_empty_input_handling(self):
        """Test that empty input displays error and re-prompts.
        
        Requirements: 4.1, 4.2
        """
        # Mock input to return empty string first, then valid query
        with patch('builtins.input', side_effect=['', 'valid query']):
            with patch('builtins.print') as mock_print:
                result = get_user_query()
                
                # Should return the valid query after re-prompting
                assert result == 'valid query'
                
                # Should have printed the error message for empty input
                mock_print.assert_called_once_with(MessageFormatter.empty_query_error())
    
    def test_whitespace_only_input_handling(self):
        """Test that whitespace-only input is treated as empty.
        
        Requirements: 4.3, 4.1, 4.2
        """
        # Mock input to return whitespace-only strings, then valid query
        with patch('builtins.input', side_effect=['   ', '\t\n', 'valid query']):
            with patch('builtins.print') as mock_print:
                result = get_user_query()
                
                # Should return the valid query after re-prompting
                assert result == 'valid query'
                
                # Should have printed error messages for both whitespace inputs
                expected_calls = [
                    call(MessageFormatter.empty_query_error()),
                    call(MessageFormatter.empty_query_error())
                ]
                mock_print.assert_has_calls(expected_calls)
    
    def test_exit_command_detection_lowercase(self):
        """Test that 'exit' command returns None.
        
        Requirements: 3.1
        """
        with patch('builtins.input', return_value='exit'):
            result = get_user_query()
            assert result is None
    
    def test_exit_command_detection_uppercase(self):
        """Test that 'EXIT' command returns None (case-insensitive).
        
        Requirements: 3.1
        """
        with patch('builtins.input', return_value='EXIT'):
            result = get_user_query()
            assert result is None
    
    def test_quit_command_detection_lowercase(self):
        """Test that 'quit' command returns None.
        
        Requirements: 3.2
        """
        with patch('builtins.input', return_value='quit'):
            result = get_user_query()
            assert result is None
    
    def test_quit_command_detection_uppercase(self):
        """Test that 'QUIT' command returns None (case-insensitive).
        
        Requirements: 3.2
        """
        with patch('builtins.input', return_value='QUIT'):
            result = get_user_query()
            assert result is None
    
    def test_quit_command_detection_mixed_case(self):
        """Test that 'QuIt' command returns None (case-insensitive).
        
        Requirements: 3.2
        """
        with patch('builtins.input', return_value='QuIt'):
            result = get_user_query()
            assert result is None
    
    def test_valid_query_input(self):
        """Test that valid query input is returned stripped.
        
        Requirements: 1.3
        """
        with patch('builtins.input', return_value='  machine learning research  '):
            result = get_user_query()
            assert result == 'machine learning research'
    
    def test_valid_query_no_whitespace(self):
        """Test that valid query without extra whitespace is returned as-is.
        
        Requirements: 1.3
        """
        with patch('builtins.input', return_value='artificial intelligence'):
            result = get_user_query()
            assert result == 'artificial intelligence'
    
    def test_eof_handling(self):
        """Test that EOF (Ctrl+D/Ctrl+Z) returns None.
        
        Requirements: 3.3 (graceful exit)
        """
        with patch('builtins.input', side_effect=EOFError):
            result = get_user_query()
            assert result is None
    
    def test_multiple_empty_inputs_before_valid(self):
        """Test handling multiple empty inputs before receiving valid input.
        
        Requirements: 4.1, 4.2
        """
        inputs = ['', '   ', '\t', '', 'final valid query']
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                result = get_user_query()
                
                # Should return the final valid query
                assert result == 'final valid query'
                
                # Should have printed error message for each empty input
                assert mock_print.call_count == 4
                for call_args in mock_print.call_args_list:
                    assert call_args[0][0] == MessageFormatter.empty_query_error()
    
    def test_exit_with_whitespace(self):
        """Test that exit command with surrounding whitespace works.
        
        Requirements: 3.1
        """
        with patch('builtins.input', return_value='  exit  '):
            result = get_user_query()
            assert result is None
    
    def test_quit_with_whitespace(self):
        """Test that quit command with surrounding whitespace works.
        
        Requirements: 3.2
        """
        with patch('builtins.input', return_value='  quit  '):
            result = get_user_query()
            assert result is None
    
    def test_query_prompt_called(self):
        """Test that the correct prompt message is displayed.
        
        Requirements: 5.4 (clear input indicators)
        """
        with patch('builtins.input', return_value='test query') as mock_input:
            result = get_user_query()
            
            # Verify input was called with the correct prompt
            mock_input.assert_called_with(MessageFormatter.query_prompt())
            assert result == 'test query'
    
    def test_empty_input_then_exit(self):
        """Test empty input followed by exit command.
        
        Requirements: 4.1, 4.2, 3.1
        """
        with patch('builtins.input', side_effect=['', 'exit']):
            with patch('builtins.print') as mock_print:
                result = get_user_query()
                
                # Should return None for exit
                assert result is None
                
                # Should have printed error for empty input
                mock_print.assert_called_once_with(MessageFormatter.empty_query_error())