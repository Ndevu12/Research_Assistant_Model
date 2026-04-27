# -*- coding: utf-8 -*-
"""Enhanced JSON processing with improved extraction and parsing.

This module provides enhanced JSON extraction and parsing capabilities,
including support for incremental parsing, better error reporting, and
recovery from common JSON formatting issues.
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from .logging_system import get_application_logger


@dataclass
class JSONParsingError:
    """Detailed JSON parsing error information."""
    error_type: str
    message: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    context: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class JSONExtractionResult:
    """Result of JSON extraction from text."""
    success: bool
    json_string: Optional[str] = None
    error: Optional[JSONParsingError] = None
    extraction_method: Optional[str] = None
    confidence_score: float = 0.0


class EnhancedJSONProcessor:
    """Enhanced JSON extraction and parsing processor."""
    
    def __init__(self):
        """Initialize JSON processor."""
        self.logger = get_application_logger()
    
    def extract_json(self, text: str) -> JSONExtractionResult:
        """Extract JSON from text with multiple strategies.
        
        Args:
            text: Text potentially containing JSON
            
        Returns:
            JSONExtractionResult: Extracted JSON or error details
        """
        # Try different extraction methods in order of preference
        methods = [
            ("direct_parse", self._try_direct_parse),
            ("bracket_matching", self._extract_by_bracket_matching),
            ("pattern_matching", self._extract_by_pattern_matching),
            ("incremental_parse", self._try_incremental_parse),
        ]
        
        for method_name, method_func in methods:
            try:
                result = method_func(text)
                if result.success:
                    result.extraction_method = method_name
                    self.logger.debug(
                        f"Successfully extracted JSON using {method_name}",
                        extra_data={'method': method_name, 'confidence': result.confidence_score}
                    )
                    return result
            except Exception as e:
                self.logger.debug(
                    f"JSON extraction method {method_name} failed: {str(e)}",
                    extra_data={'method': method_name, 'error': str(e)}
                )
                continue
        
        # If all methods fail, return error
        return JSONExtractionResult(
            success=False,
            error=JSONParsingError(
                error_type="extraction_failed",
                message="Could not extract valid JSON from text using any method",
                suggestion="Ensure the response contains valid JSON format"
            ),
            confidence_score=0.0
        )
    
    def _try_direct_parse(self, text: str) -> JSONExtractionResult:
        """Try to parse text directly as JSON.
        
        Args:
            text: Text to parse
            
        Returns:
            JSONExtractionResult: Parse result
        """
        text = text.strip()
        try:
            parsed = json.loads(text)
            return JSONExtractionResult(
                success=True,
                json_string=text,
                confidence_score=1.0
            )
        except json.JSONDecodeError as e:
            return JSONExtractionResult(
                success=False,
                error=JSONParsingError(
                    error_type="json_syntax",
                    message=str(e),
                    line_number=e.lineno,
                    column_number=e.colno
                ),
                confidence_score=0.0
            )
    
    def _extract_by_bracket_matching(self, text: str) -> JSONExtractionResult:
        """Extract JSON by matching brackets.
        
        Args:
            text: Text to search
            
        Returns:
            JSONExtractionResult: Extraction result
        """
        # Find first { or [
        start_idx = -1
        start_char = None
        
        for i, char in enumerate(text):
            if char == '{':
                start_idx = i
                start_char = '{'
                break
            elif char == '[':
                start_idx = i
                start_char = '['
                break
        
        if start_idx == -1:
            return JSONExtractionResult(
                success=False,
                error=JSONParsingError(
                    error_type="no_json_found",
                    message="No JSON structure found in text"
                ),
                confidence_score=0.0
            )
        
        # Find matching closing bracket
        end_char = '}' if start_char == '{' else ']'
        bracket_count = 0
        end_idx = -1
        in_string = False
        escape_next = False
        
        for i in range(start_idx, len(text)):
            char = text[i]
            
            # Handle string escaping
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            # Track string state
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            # Count brackets only outside strings
            if not in_string:
                if char == start_char:
                    bracket_count += 1
                elif char == end_char:
                    bracket_count -= 1
                    if bracket_count == 0:
                        end_idx = i + 1
                        break
        
        if end_idx == -1:
            return JSONExtractionResult(
                success=False,
                error=JSONParsingError(
                    error_type="unmatched_brackets",
                    message="Could not find matching closing bracket"
                ),
                confidence_score=0.0
            )
        
        # Extract and try to parse
        json_string = text[start_idx:end_idx]
        try:
            parsed = json.loads(json_string)
            return JSONExtractionResult(
                success=True,
                json_string=json_string,
                confidence_score=0.9
            )
        except json.JSONDecodeError as e:
            return JSONExtractionResult(
                success=False,
                error=JSONParsingError(
                    error_type="json_syntax",
                    message=str(e),
                    line_number=e.lineno,
                    column_number=e.colno
                ),
                confidence_score=0.0
            )
    
    def _extract_by_pattern_matching(self, text: str) -> JSONExtractionResult:
        """Extract JSON using regex patterns.
        
        Args:
            text: Text to search
            
        Returns:
            JSONExtractionResult: Extraction result
        """
        # Try to find JSON-like patterns
        patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested objects
            r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]',  # Nested arrays
            r'\{.*\}',  # Simple object
            r'\[.*\]',  # Simple array
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                json_string = match.group(0)
                try:
                    parsed = json.loads(json_string)
                    return JSONExtractionResult(
                        success=True,
                        json_string=json_string,
                        confidence_score=0.7
                    )
                except json.JSONDecodeError:
                    continue
        
        return JSONExtractionResult(
            success=False,
            error=JSONParsingError(
                error_type="pattern_match_failed",
                message="No valid JSON patterns found"
            ),
            confidence_score=0.0
        )
    
    def _try_incremental_parse(self, text: str) -> JSONExtractionResult:
        """Try incremental parsing for large responses.
        
        Args:
            text: Text to parse
            
        Returns:
            JSONExtractionResult: Extraction result
        """
        # Try to find and parse multiple JSON objects
        json_objects = []
        current_obj = ""
        bracket_count = 0
        in_string = False
        escape_next = False
        
        for char in text:
            if escape_next:
                escape_next = False
                current_obj += char
                continue
            
            if char == '\\':
                escape_next = True
                current_obj += char
                continue
            
            if char == '"':
                in_string = not in_string
                current_obj += char
                continue
            
            if not in_string:
                if char in '{[':
                    bracket_count += 1
                elif char in '}]':
                    bracket_count -= 1
            
            current_obj += char
            
            # Try to parse when bracket count returns to 0
            if bracket_count == 0 and current_obj.strip():
                try:
                    parsed = json.loads(current_obj)
                    json_objects.append(current_obj)
                    current_obj = ""
                except json.JSONDecodeError:
                    pass
        
        if json_objects:
            # Return the first valid JSON object
            return JSONExtractionResult(
                success=True,
                json_string=json_objects[0],
                confidence_score=0.8
            )
        
        return JSONExtractionResult(
            success=False,
            error=JSONParsingError(
                error_type="incremental_parse_failed",
                message="Could not parse any complete JSON objects"
            ),
            confidence_score=0.0
        )
    
    def parse_json(self, json_string: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[JSONParsingError]]:
        """Parse JSON string with detailed error reporting.
        
        Args:
            json_string: JSON string to parse
            
        Returns:
            Tuple[bool, Optional[Dict], Optional[JSONParsingError]]: Success, parsed data, error
        """
        try:
            parsed = json.loads(json_string)
            return True, parsed, None
        except json.JSONDecodeError as e:
            # Get context around error
            lines = json_string.split('\n')
            context_lines = []
            if e.lineno and e.lineno > 0:
                start = max(0, e.lineno - 2)
                end = min(len(lines), e.lineno + 1)
                context_lines = lines[start:end]
            
            context = '\n'.join(context_lines) if context_lines else None
            
            # Generate suggestion
            suggestion = self._suggest_fix(json_string, e)
            
            error = JSONParsingError(
                error_type="json_syntax",
                message=str(e),
                line_number=e.lineno,
                column_number=e.colno,
                context=context,
                suggestion=suggestion
            )
            
            return False, None, error
    
    def _suggest_fix(self, json_string: str, error: json.JSONDecodeError) -> Optional[str]:
        """Suggest a fix for JSON parsing error.
        
        Args:
            json_string: The JSON string that failed
            error: The JSONDecodeError
            
        Returns:
            Optional[str]: Suggested fix or None
        """
        error_msg = str(error).lower()
        
        if "expecting property name" in error_msg:
            return "Check for missing quotes around property names"
        elif "expecting value" in error_msg:
            return "Check for missing or invalid values"
        elif "trailing comma" in error_msg or "extra data" in error_msg:
            return "Remove trailing commas before closing brackets"
        elif "unterminated string" in error_msg:
            return "Check for unclosed string literals"
        elif "invalid escape" in error_msg:
            return "Check for invalid escape sequences in strings"
        
        return None
    
    def pretty_print_json(self, json_string: str, indent: int = 2) -> Optional[str]:
        """Pretty print JSON string.
        
        Args:
            json_string: JSON string to format
            indent: Indentation level
            
        Returns:
            Optional[str]: Formatted JSON or None if invalid
        """
        try:
            parsed = json.loads(json_string)
            return json.dumps(parsed, indent=indent, ensure_ascii=False)
        except json.JSONDecodeError:
            return None
    
    def validate_json_structure(self, json_string: str, schema: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str]]:
        """Validate JSON structure against optional schema.
        
        Args:
            json_string: JSON string to validate
            schema: Optional schema to validate against
            
        Returns:
            Tuple[bool, List[str]]: Valid status and list of errors
        """
        try:
            parsed = json.loads(json_string)
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {str(e)}"]
        
        errors = []
        
        # Basic structure validation
        if not isinstance(parsed, (dict, list)):
            errors.append("JSON must be an object or array at root level")
        
        # Schema validation if provided
        if schema:
            errors.extend(self._validate_against_schema(parsed, schema))
        
        return len(errors) == 0, errors
    
    def _validate_against_schema(self, data: Any, schema: Dict[str, Any]) -> List[str]:
        """Validate data against schema.
        
        Args:
            data: Data to validate
            schema: Schema to validate against
            
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        
        # Check required fields
        if "required" in schema:
            if isinstance(data, dict):
                for field in schema["required"]:
                    if field not in data:
                        errors.append(f"Missing required field: {field}")
        
        # Check field types
        if "properties" in schema and isinstance(data, dict):
            for field, field_schema in schema["properties"].items():
                if field in data:
                    expected_type = field_schema.get("type")
                    if expected_type and not self._check_type(data[field], expected_type):
                        errors.append(f"Field '{field}' has wrong type: expected {expected_type}")
        
        return errors
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type.
        
        Args:
            value: Value to check
            expected_type: Expected type name
            
        Returns:
            bool: True if type matches
        """
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, assume valid
        
        return isinstance(value, expected)


# Global JSON processor instance
_json_processor: Optional[EnhancedJSONProcessor] = None


def get_json_processor() -> EnhancedJSONProcessor:
    """Get the global JSON processor.
    
    Returns:
        EnhancedJSONProcessor: Global processor instance
    """
    global _json_processor
    if _json_processor is None:
        _json_processor = EnhancedJSONProcessor()
    return _json_processor


def extract_json(text: str) -> JSONExtractionResult:
    """Extract JSON from text.
    
    Args:
        text: Text to extract JSON from
        
    Returns:
        JSONExtractionResult: Extraction result
    """
    processor = get_json_processor()
    return processor.extract_json(text)


def parse_json(json_string: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[JSONParsingError]]:
    """Parse JSON string.
    
    Args:
        json_string: JSON string to parse
        
    Returns:
        Tuple[bool, Optional[Dict], Optional[JSONParsingError]]: Parse result
    """
    processor = get_json_processor()
    return processor.parse_json(json_string)


def pretty_print_json(json_string: str, indent: int = 2) -> Optional[str]:
    """Pretty print JSON.
    
    Args:
        json_string: JSON string to format
        indent: Indentation level
        
    Returns:
        Optional[str]: Formatted JSON
    """
    processor = get_json_processor()
    return processor.pretty_print_json(json_string, indent)