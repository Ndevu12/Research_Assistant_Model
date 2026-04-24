# -*- coding: utf-8 -*-
"""Message formatting utilities for consistent user interface.

This module provides utilities for consistent formatting of all user-facing
messages in the AI Research Assistant, ensuring a cohesive user experience.
"""


class MessageFormatter:
    """Utility class for consistent message formatting."""
    
    # Standard separators
    MAJOR_SEPARATOR = "=" * 60
    MINOR_SEPARATOR = "-" * 60
    
    # Standard prefixes
    ERROR_PREFIX = "❌ Error:"
    SUCCESS_PREFIX = "✅"
    INFO_PREFIX = "ℹ️"
    
    @classmethod
    def welcome_message(cls) -> str:
        """Format the welcome message for interactive mode.
        
        Returns:
            str: Formatted welcome message with instructions.
        """
        return (
            f"{cls.MAJOR_SEPARATOR}\n"
            "Welcome to the AI Research Assistant!\n"
            f"{cls.MAJOR_SEPARATOR}\n"
            "\nHow to use:\n"
            "  • Enter your research query when prompted\n"
            "  • Type 'exit' or 'quit' to end your session\n"
            "  • Press Ctrl+C to exit at any time\n"
        )
    
    @classmethod
    def farewell_message(cls) -> str:
        """Format the farewell message for session exit.
        
        Returns:
            str: Formatted farewell message.
        """
        return "\nThank you for using the AI Research Assistant. Goodbye!"
    
    @classmethod
    def query_prompt(cls) -> str:
        """Format the query input prompt.
        
        Returns:
            str: Formatted query prompt.
        """
        return "Enter your research query (or 'exit'/'quit' to quit): "
    
    @classmethod
    def error_message(cls, message: str) -> str:
        """Format an error message with consistent styling.
        
        Args:
            message: The error message content.
            
        Returns:
            str: Formatted error message.
        """
        return f"{cls.ERROR_PREFIX} {message}"
    
    @classmethod
    def empty_query_error(cls) -> str:
        """Format the empty query error message.
        
        Returns:
            str: Formatted empty query error message.
        """
        return cls.error_message("Query cannot be empty. Please enter a valid research query.")
    
    @classmethod
    def result_separator(cls) -> str:
        """Format the separator between query results.
        
        Returns:
            str: Formatted result separator.
        """
        return f"\n{cls.MINOR_SEPARATOR}\n"
    
    @classmethod
    def network_error(cls, error: str) -> str:
        """Format network-related error messages.
        
        Args:
            error: The error description.
            
        Returns:
            str: Formatted network error message.
        """
        return (
            f"Error fetching papers: {error}\n"
            "Check your internet connection and try again."
        )
    
    @classmethod
    def no_results_message(cls) -> str:
        """Format the no results found message.
        
        Returns:
            str: Formatted no results message.
        """
        return "No papers found. Try a different query."
    
    @classmethod
    def parsing_error(cls, error: str) -> str:
        """Format parsing error messages.
        
        Args:
            error: The parsing error description.
            
        Returns:
            str: Formatted parsing error message.
        """
        return f"{cls.ERROR_PREFIX} Parsing Error: {error}"
    
    @classmethod
    def json_syntax_error(cls, error: str, line: int = None, column: int = None) -> str:
        """Format JSON syntax error messages with specific location information.
        
        Args:
            error: The JSON syntax error description.
            line: Line number where the error occurred (if available).
            column: Column number where the error occurred (if available).
            
        Returns:
            str: Formatted JSON syntax error message.
        """
        location_info = ""
        if line is not None and column is not None:
            location_info = f" at line {line}, column {column}"
        elif line is not None:
            location_info = f" at line {line}"
        
        return f"{cls.ERROR_PREFIX} Parsing Error: JSON Syntax{location_info} - {error}"
    
    @classmethod
    def schema_validation_error(cls, error: str) -> str:
        """Format schema validation error messages.
        
        Args:
            error: The schema validation error description.
            
        Returns:
            str: Formatted schema validation error message.
        """
        return f"{cls.ERROR_PREFIX} Parsing Error: Schema Validation - {error}"
    
    @classmethod
    def field_type_error(cls, field_name: str, expected_type: str, actual_type: str) -> str:
        """Format field type error messages.
        
        Args:
            field_name: Name of the field with incorrect type.
            expected_type: Expected data type.
            actual_type: Actual data type found.
            
        Returns:
            str: Formatted field type error message.
        """
        return f"{cls.ERROR_PREFIX} Parsing Error: Field Type - '{field_name}' must be a {expected_type}, got {actual_type}"
    
    @classmethod
    def structure_error(cls, error: str) -> str:
        """Format JSON structure error messages.
        
        Args:
            error: The structure error description.
            
        Returns:
            str: Formatted structure error message.
        """
        return f"{cls.ERROR_PREFIX} Parsing Error: Structure - {error}"
    
    @classmethod
    def extraction_error(cls, error: str) -> str:
        """Format JSON extraction error messages.
        
        Args:
            error: The extraction error description.
            
        Returns:
            str: Formatted extraction error message.
        """
        return f"{cls.ERROR_PREFIX} Parsing Error: Extraction - {error}"
    
    @classmethod
    def validation_error(cls, error: str) -> str:
        """Format general validation error messages.
        
        Args:
            error: The validation error description.
            
        Returns:
            str: Formatted validation error message.
        """
        return f"{cls.ERROR_PREFIX} Parsing Error: Validation - {error}"
    
    @classmethod
    def raw_response_header(cls) -> str:
        """Format the raw response header for debugging.
        
        Returns:
            str: Formatted raw response header.
        """
        return "-- RAW RESPONSE FROM LLM --"
    
    @classmethod
    def partial_recovery_header(cls) -> str:
        """Format the partial data recovery header.
        
        Returns:
            str: Formatted partial recovery header.
        """
        return f"{cls.INFO_PREFIX} Attempting partial data recovery..."
    
    @classmethod
    def recovery_success_message(cls, recovered_items: list[str]) -> str:
        """Format successful partial recovery message.
        
        Args:
            recovered_items: List of items that were successfully recovered.
            
        Returns:
            str: Formatted recovery success message.
        """
        items_text = ", ".join(recovered_items)
        return f"{cls.SUCCESS_PREFIX} Partial recovery successful: {items_text}. Please try your query again."
    
    @classmethod
    def recovery_failure_message(cls) -> str:
        """Format partial recovery failure message.
        
        Returns:
            str: Formatted recovery failure message.
        """
        return f"{cls.ERROR_PREFIX} Could not recover partial data from malformed response."
    
    @classmethod
    def debugging_suggestion(cls, error_type: str) -> str:
        """Format debugging suggestions for different error types.
        
        Args:
            error_type: The type of error (syntax, validation, extraction, etc.).
            
        Returns:
            str: Formatted debugging suggestion.
        """
        suggestions = {
            "syntax": "The LLM response contains invalid JSON syntax. Check for missing commas, brackets, or quotes.",
            "validation": "The JSON structure is missing required fields or has incorrect data types.",
            "extraction": "Could not find valid JSON in the LLM response. The response may be conversational text.",
            "structure": "The response is not a JSON object or has an unexpected format.",
            "field_type": "A required field has the wrong data type. Check the field structure in the raw response.",
            "schema": "The JSON doesn't match the expected schema with 'query' and 'papers' fields."
        }
        
        suggestion = suggestions.get(error_type, "Review the raw response below for debugging information.")
        return f"{cls.INFO_PREFIX} Debugging hint: {suggestion}"
    
    @classmethod
    def api_retry_message(cls, service: str, attempt: int, error: str) -> str:
        """Format API retry messages.
        
        Args:
            service: The API service name.
            attempt: The attempt number.
            error: The error description.
            
        Returns:
            str: Formatted retry message.
        """
        return f"{service} attempt {attempt} failed: {error}. Retrying..."
    
    @classmethod
    def api_rate_limit_message(cls, service: str, wait_time: str) -> str:
        """Format API rate limit messages.
        
        Args:
            service: The API service name.
            wait_time: The wait time in seconds.
            
        Returns:
            str: Formatted rate limit message.
        """
        return f"{service} rate limited. Waiting {wait_time}s..."
    
    @classmethod
    def api_max_retries_message(cls, service: str) -> str:
        """Format API max retries exceeded messages.
        
        Args:
            service: The API service name.
            
        Returns:
            str: Formatted max retries message.
        """
        return f"{service}: Max retries exceeded. Skipping this source."