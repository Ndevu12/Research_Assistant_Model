# -*- coding: utf-8 -*-
"""Enhanced validation with retry strategy classification.

This module extends the existing validation system with retry strategy
classification while preserving all existing validation logic.
"""

from typing import Optional

from .response_models import ValidationResult, RetryStrategy, RecoveryResult, RecoveryConfig
from .retry_manager import RetryManager


def _classify_error_for_retry(validation_result: ValidationResult) -> Optional[RetryStrategy]:
    """Classify validation errors to determine optimal retry strategy.
    
    Extends existing validation with retry-specific classification.
    
    Args:
        validation_result: Result from existing _validate_json_structure
        
    Returns:
        RetryStrategy: Recommended retry strategy, or None if no retry recommended
    """
    if not validation_result.is_valid:
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
    
    return None


def enhance_validation_result(validation_result: ValidationResult) -> ValidationResult:
    """Enhance existing validation result with retry strategy classification.
    
    This function takes the result from the existing _validate_json_structure
    function and adds retry strategy information without changing the core
    validation logic.
    
    Args:
        validation_result: Original validation result
        
    Returns:
        ValidationResult: Enhanced validation result with retry strategy
    """
    # Create enhanced result with retry strategy
    enhanced_result = ValidationResult(
        is_valid=validation_result.is_valid,
        error_message=validation_result.error_message,
        error_type=validation_result.error_type,
        show_raw_response=validation_result.show_raw_response,
        retry_strategy=_classify_error_for_retry(validation_result)
    )
    
    return enhanced_result


def should_attempt_retry(validation_result: ValidationResult, attempt_count: int, retry_manager: RetryManager) -> bool:
    """Determine if retry should be attempted based on validation result.
    
    Args:
        validation_result: Result from validation
        attempt_count: Current attempt number
        retry_manager: Retry manager instance
        
    Returns:
        bool: True if retry should be attempted
    """
    if validation_result.is_valid:
        return False
        
    return retry_manager.should_retry(validation_result.error_type, attempt_count)


def get_enhanced_prompt_for_retry(
    original_prompt: str, 
    validation_result: ValidationResult, 
    retry_manager: RetryManager,
    previous_response: str = ""
) -> str:
    """Get enhanced prompt for retry based on validation result.
    
    Args:
        original_prompt: The original prompt that failed
        validation_result: Validation result with error details
        retry_manager: Retry manager instance
        previous_response: Previous response that failed
        
    Returns:
        str: Enhanced prompt for retry
    """
    return retry_manager.enhance_prompt(
        original_prompt, 
        validation_result.error_type, 
        previous_response
    )


def _enhanced_partial_recovery(
    raw_output: str,
    clean_json: str,
    parsed_data,
    config: RecoveryConfig,
    user_query: str = ""
) -> RecoveryResult:
    """Enhanced partial recovery with fallback processing.
    
    This function wraps the existing _attempt_partial_recovery with enhanced
    fallback processing capabilities.
    
    Args:
        raw_output: Original model output
        clean_json: Cleaned JSON string
        parsed_data: Partially parsed data
        config: Recovery configuration
        user_query: Original user query for context
        
    Returns:
        RecoveryResult: Enhanced recovery result
    """
    try:
        from .fallback_processing import enhance_partial_recovery_with_fallback
        return enhance_partial_recovery_with_fallback(
            raw_output, clean_json, parsed_data, config, user_query
        )
    except ImportError:
        # Fallback processing not available, use existing recovery
        from ..retrieval.helpers_modules.recovery import enhanced_partial_recovery
        return enhanced_partial_recovery(raw_output, clean_json, parsed_data)