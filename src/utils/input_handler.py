# -*- coding: utf-8 -*-
"""Input handler for interactive user prompts.

This module provides functionality for prompting users for research queries
and validating their input in interactive mode.
"""

from .message_formatter import MessageFormatter

try:
    # Enables arrow-key line editing and in-session history for input().
    import readline  # noqa: F401
except ImportError:  # pragma: no cover - unavailable on some platforms
    readline = None


def get_user_query() -> str | None:
    """Prompt user for a research query and validate input.
    
    Prompts the user to enter a research query, validates the input,
    and handles exit commands. Empty or whitespace-only input triggers
    an error message and re-prompts the user.
    
    Returns:
        str: The stripped query string if valid input is provided.
        None: If the user enters an exit command ("exit" or "quit").
    
    Requirements:
        - 1.3: Process user-entered queries
        - 4.1: Display error message for empty queries
        - 4.2: Re-prompt for valid query after empty input
        - 4.3: Treat whitespace-only input as empty
    """
    while True:
        try:
            query = input(MessageFormatter.query_prompt()).strip()
            
            # Check for exit commands (case-insensitive)
            if query.lower() in ("exit", "quit"):
                return None
            
            # Validate non-empty input
            if not query:
                print(MessageFormatter.empty_query_error())
                continue
            
            return query
            
        except EOFError:
            # Handle EOF (Ctrl+D on Unix, Ctrl+Z on Windows)
            return None
