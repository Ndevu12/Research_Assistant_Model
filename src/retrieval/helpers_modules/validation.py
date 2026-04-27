# -*- coding: utf-8 -*-
"""Validation utilities for orchestrator."""

from dataclasses import dataclass
from typing import Optional

from ...utils.message_formatter import MessageFormatter
from ...utils.response_models import RetryStrategy


@dataclass
class ValidationResult:
    """Result of JSON structure validation."""
    is_valid: bool
    error_message: str = ""
    error_type: str = ""
    show_raw_response: bool = True
    retry_strategy: Optional[RetryStrategy] = None


def validate_json_structure(parsed_data: any) -> ValidationResult:
    """Validate JSON structure with comprehensive checks and graceful degradation.
    
    Performs layered validation to ensure data integrity before model validation.
    Provides specific error messages for each type of validation failure.
    
    Args:
        parsed_data: The parsed JSON data to validate
        
    Returns:
        ValidationResult: Validation result with error details if invalid
    """
    # Check 1: Must be a dictionary (JSON object)
    if not isinstance(parsed_data, dict):
        actual_type = type(parsed_data).__name__
        return ValidationResult(
            is_valid=False,
            error_message=MessageFormatter.structure_error(
                f"Response must be a JSON object, got {actual_type}"
            ),
            error_type="structure"
        )
    
    # Check 2: Must have required fields
    required_fields = ["query", "papers"]
    missing_fields = [field for field in required_fields if field not in parsed_data]
    
    if missing_fields:
        available_fields = list(parsed_data.keys())
        return ValidationResult(
            is_valid=False,
            error_message=MessageFormatter.schema_validation_error(
                f"Missing required fields: {missing_fields}. "
                f"Expected 'query' and 'papers', got: {available_fields}"
            ),
            error_type="schema"
        )
    
    # Check 3: Validate "query" field type
    query_value = parsed_data["query"]
    if not isinstance(query_value, str):
        actual_type = type(query_value).__name__
        return ValidationResult(
            is_valid=False,
            error_message=MessageFormatter.field_type_error(
                "query", "string", actual_type
            ),
            error_type="field_type"
        )
    
    # Check 4: Validate "papers" field type
    papers_value = parsed_data["papers"]
    if not isinstance(papers_value, list):
        actual_type = type(papers_value).__name__
        return ValidationResult(
            is_valid=False,
            error_message=MessageFormatter.field_type_error(
                "papers", "list", actual_type
            ),
            error_type="field_type"
        )
    
    # Check 5: Validate each paper object structure
    for i, paper in enumerate(papers_value):
        if not isinstance(paper, dict):
            actual_type = type(paper).__name__
            return ValidationResult(
                is_valid=False,
                error_message=MessageFormatter.structure_error(
                    f"Paper at index {i} must be an object, got {actual_type}"
                ),
                error_type="structure"
            )
        
        # Check required paper fields
        if "title" not in paper:
            return ValidationResult(
                is_valid=False,
                error_message=MessageFormatter.schema_validation_error(
                    f"Paper at index {i} missing required 'title' field"
                ),
                error_type="schema"
            )
        
        # Validate title is a string
        if not isinstance(paper["title"], str):
            actual_type = type(paper["title"]).__name__
            return ValidationResult(
                is_valid=False,
                error_message=MessageFormatter.field_type_error(
                    f"papers[{i}].title", "string", actual_type
                ),
                error_type="field_type"
            )
        
        # Validate optional fields have correct types when present
        optional_string_fields = ["venue", "url", "doi"]
        for field in optional_string_fields:
            if field in paper and paper[field] is not None and not isinstance(paper[field], str):
                actual_type = type(paper[field]).__name__
                return ValidationResult(
                    is_valid=False,
                    error_message=MessageFormatter.field_type_error(
                        f"papers[{i}].{field}", "string or null", actual_type
                    ),
                    error_type="field_type"
                )
        
        # Validate year is integer when present
        if "year" in paper and paper["year"] is not None and not isinstance(paper["year"], int):
            actual_type = type(paper["year"]).__name__
            return ValidationResult(
                is_valid=False,
                error_message=MessageFormatter.field_type_error(
                    f"papers[{i}].year", "integer or null", actual_type
                ),
                error_type="field_type"
            )
        
        # Validate list fields have correct types when present
        list_fields = ["key_points", "why_relevant"]
        for field in list_fields:
            if field in paper:
                if not isinstance(paper[field], list):
                    actual_type = type(paper[field]).__name__
                    return ValidationResult(
                        is_valid=False,
                        error_message=MessageFormatter.field_type_error(
                            f"papers[{i}].{field}", "list", actual_type
                        ),
                        error_type="field_type"
                    )
                
                # Validate all items in list are strings
                for j, item in enumerate(paper[field]):
                    if not isinstance(item, str):
                        actual_type = type(item).__name__
                        return ValidationResult(
                            is_valid=False,
                            error_message=MessageFormatter.field_type_error(
                                f"papers[{i}].{field}[{j}]", "string", actual_type
                            ),
                            error_type="field_type"
                        )
    
    # All validation checks passed
    return ValidationResult(is_valid=True)


def enhance_validation_with_retry_strategy(validation_result: ValidationResult) -> ValidationResult:
    """Enhance existing validation result with retry strategy classification.
    
    This function adds retry strategy information to validation results without
    changing the core validation logic, preserving backward compatibility.
    
    Args:
        validation_result: Original validation result from validate_json_structure
        
    Returns:
        ValidationResult: Enhanced validation result with retry strategy
    """
    if not validation_result.is_valid:
        # Classify error for retry strategy
        if validation_result.error_type == "syntax":
            validation_result.retry_strategy = RetryStrategy.SYNTAX_EMPHASIS
        elif validation_result.error_type == "schema":
            validation_result.retry_strategy = RetryStrategy.SCHEMA_EXAMPLE
        elif validation_result.error_type == "field_type":
            validation_result.retry_strategy = RetryStrategy.TYPE_CLARIFICATION
        elif validation_result.error_type == "structure":
            validation_result.retry_strategy = RetryStrategy.FORMAT_INSTRUCTION
        else:
            validation_result.retry_strategy = RetryStrategy.GENERIC_CLARIFICATION
    
    return validation_result
