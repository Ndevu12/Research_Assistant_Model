# -*- coding: utf-8 -*-
"""Retry management for graceful response handling.

This module implements intelligent retry strategies that enhance prompts based
on specific error types detected during response processing.
"""

import asyncio
import time
from typing import Optional

from .response_models import (
    RetryConfig, RetryStrategy, RequestContext, ValidationResult
)


class RetryManager:
    """Progressive retry mechanism that enhances prompts based on error analysis."""
    
    def __init__(self, config: RetryConfig):
        """Initialize retry manager with configuration.
        
        Args:
            config: Retry configuration settings
        """
        self.config = config
        
    def should_retry(self, error_type: str, attempt_count: int) -> bool:
        """Determine if retry is appropriate for the given error type and attempt count.
        
        Args:
            error_type: The type of error that occurred
            attempt_count: Current attempt number (0-based)
            
        Returns:
            bool: True if retry should be attempted
        """
        if attempt_count >= self.config.max_retries:
            return False
            
        return error_type in self.config.enabled_for_errors
    
    def enhance_prompt(
        self, 
        original_prompt: str, 
        error_type: str,
        previous_response: str = ""
    ) -> str:
        """Enhance prompt based on specific error type from existing validation.
        
        Args:
            original_prompt: The original prompt that failed
            error_type: Type of error detected (from existing validation)
            previous_response: The previous response that failed (for context)
            
        Returns:
            str: Enhanced prompt with specific instructions
        """
        if error_type == "syntax":
            return self._add_syntax_emphasis(original_prompt)
        elif error_type == "schema":
            return self._add_schema_example(original_prompt)
        elif error_type == "field_type":
            return self._add_type_clarification(original_prompt)
        elif error_type == "structure":
            return self._add_format_instruction(original_prompt)
        else:
            return self._add_generic_clarification(original_prompt)
    
    def enhance_prompt_for_syntax_error(self, original_prompt: str, error_details: str) -> str:
        """Enhance prompt specifically for JSON syntax errors.
        
        Args:
            original_prompt: The original prompt
            error_details: Details about the syntax error
            
        Returns:
            str: Enhanced prompt with syntax emphasis
        """
        syntax_instruction = (
            "\n\nCRITICAL: The previous response had JSON syntax errors. "
            "You MUST respond with ONLY valid JSON. "
            "Common issues to avoid:\n"
            "- Missing commas between fields\n"
            "- Missing quotes around strings\n"
            "- Unescaped quotes within strings\n"
            "- Missing closing brackets or braces\n"
            "- No text before or after the JSON object\n"
            f"Previous error: {error_details[:100]}..."
        )
        return original_prompt + syntax_instruction
    
    def enhance_prompt_generic(self, original_prompt: str, error_details: str) -> str:
        """Generic prompt enhancement for unknown errors.
        
        Args:
            original_prompt: The original prompt
            error_details: Details about the error
            
        Returns:
            str: Enhanced prompt with generic clarification
        """
        generic_instruction = (
            "\n\nIMPORTANT: The previous response could not be processed correctly. "
            "Please ensure your response is valid JSON with the exact structure requested. "
            "Do not include any conversational text or explanations outside the JSON."
        )
        return original_prompt + generic_instruction
    
    def _add_syntax_emphasis(self, prompt: str) -> str:
        """Add JSON syntax emphasis to prompt."""
        syntax_instruction = (
            "\n\nIMPORTANT: Respond with ONLY valid JSON. "
            "Ensure proper commas, brackets, and quotes. "
            "Do not include any text before or after the JSON object. "
            "Example format: {\"query\": \"...\", \"papers\": [...]}"
        )
        return prompt + syntax_instruction
    
    def _add_schema_example(self, prompt: str) -> str:
        """Add schema example to prompt."""
        schema_example = (
            '\n\nRequired JSON format:\n'
            '{\n'
            '  "query": "user query string",\n'
            '  "papers": [\n'
            '    {\n'
            '      "title": "paper title",\n'
            '      "year": 2023,\n'
            '      "venue": "venue name",\n'
            '      "url": "paper url",\n'
            '      "doi": "paper doi",\n'
            '      "key_points": ["point 1", "point 2"],\n'
            '      "why_relevant": ["reason 1", "reason 2"]\n'
            '    }\n'
            '  ]\n'
            '}\n'
            'You MUST include both "query" and "papers" fields.'
        )
        return prompt + schema_example
    
    def _add_type_clarification(self, prompt: str) -> str:
        """Add type clarification to prompt."""
        type_instruction = (
            "\n\nField type requirements:\n"
            "- query: must be a string\n"
            "- papers: must be an array/list\n"
            "- title: must be a string\n"
            "- year: must be a number (integer) or null\n"
            "- venue, url, doi: must be strings or null\n"
            "- key_points, why_relevant: must be arrays of strings\n"
            "Ensure all fields have the correct data types."
        )
        return prompt + type_instruction
    
    def _add_format_instruction(self, prompt: str) -> str:
        """Add format instruction to prompt."""
        format_instruction = (
            "\n\nFormat requirements:\n"
            "- Response must be a JSON object (starts with { and ends with })\n"
            "- Must contain exactly two top-level fields: 'query' and 'papers'\n"
            "- No additional fields at the top level\n"
            "- No conversational text outside the JSON\n"
            "- No code block markers (```json or ```)"
        )
        return prompt + format_instruction
    
    def _add_generic_clarification(self, prompt: str) -> str:
        """Add generic clarification to prompt."""
        generic_instruction = (
            "\n\nPlease ensure your response:\n"
            "- Is valid JSON format\n"
            "- Contains the required 'query' and 'papers' fields\n"
            "- Has no text outside the JSON object\n"
            "- Uses proper JSON syntax (commas, quotes, brackets)"
        )
        return prompt + generic_instruction
    
    async def get_retry_delay(self, attempt_count: int) -> float:
        """Calculate exponential backoff delay for retry attempts.
        
        Args:
            attempt_count: Current attempt number (0-based)
            
        Returns:
            float: Delay in seconds
        """
        if attempt_count == 0:
            return 0.0
            
        # Exponential backoff: base_delay * 2^(attempt_count - 1)
        delay = self.config.base_delay * (2 ** (attempt_count - 1))
        return min(delay, self.config.max_delay)
    
    def classify_error_for_retry(self, validation_result: ValidationResult) -> RetryStrategy:
        """Classify validation errors to determine optimal retry strategy.
        
        Extends existing validation with retry-specific classification.
        
        Args:
            validation_result: Result from existing validation
            
        Returns:
            RetryStrategy: Recommended retry strategy
        """
        if validation_result.error_type == "syntax":
            return RetryStrategy.SYNTAX_EMPHASIS
        elif validation_result.error_type == "schema":
            return RetryStrategy.SCHEMA_EXAMPLE
        elif validation_result.error_type == "field_type":
            return RetryStrategy.TYPE_CLARIFICATION
        elif validation_result.error_type == "structure":
            return RetryStrategy.FORMAT_INSTRUCTION
        else:
            return RetryStrategy.GENERIC_CLARIFICATION
    
    def get_retry_context(self, context: RequestContext, error_type: str) -> RequestContext:
        """Create updated context for retry attempt.
        
        Args:
            context: Original request context
            error_type: Type of error that triggered retry
            
        Returns:
            RequestContext: Updated context for retry
        """
        new_context = RequestContext(
            user_query=context.user_query,
            model_name=context.model_name,
            attempt_count=context.attempt_count + 1,
            previous_errors=context.previous_errors + [error_type],
            timestamp=context.timestamp,
            session_id=context.session_id
        )
        return new_context