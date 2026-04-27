# -*- coding: utf-8 -*-
"""JSON extraction and cleaning utilities for orchestrator."""

import re
from typing import List


def extract_and_clean_json(raw_output: str) -> str:
    """Extract and clean JSON from LLM response with enhanced pattern matching.
    
    Handles multiple code block formats, mixed content, and various LLM response patterns.
    
    Args:
        raw_output: Raw LLM response string
        
    Returns:
        str: Cleaned JSON string ready for parsing
        
    Raises:
        ValueError: If no valid JSON can be extracted
    """
    # Normalize whitespace and line endings
    normalized = re.sub(r'\r\n|\r', '\n', raw_output.strip())
    
    # Pattern 1: Try to extract JSON from code blocks with various formats
    # Matches ```json, ```, and other code block variations
    code_block_patterns = [
        r'```(?:json)?\s*\n?(.*?)\n?```',  # ```json or ``` with optional newlines
        r'`{3,}\s*(?:json)?\s*\n?(.*?)\n?`{3,}',  # Multiple backticks
        r'~~~(?:json)?\s*\n?(.*?)\n?~~~',  # Alternative code block syntax
    ]
    
    for pattern in code_block_patterns:
        matches = re.findall(pattern, normalized, re.DOTALL | re.IGNORECASE)
        for match in matches:
            candidate = match.strip()
            if _looks_like_json(candidate):
                return _normalize_json_formatting(candidate)
    
    # Pattern 2: Try to extract JSON from mixed content
    # Look for JSON-like structures in the text
    json_patterns = [
        r'\{[^{}]*"query"[^{}]*"papers"[^{}]*\}',  # Simple single-level JSON
        r'\{(?:[^{}]|\{[^{}]*\})*"query"(?:[^{}]|\{[^{}]*\})*"papers"(?:[^{}]|\{[^{}]*\})*\}',  # Nested JSON
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, normalized, re.DOTALL)
        for match in matches:
            candidate = match.strip()
            if _looks_like_json(candidate):
                return _normalize_json_formatting(candidate)
    
    # Pattern 3: Try to find JSON by looking for balanced braces
    # Find the largest balanced JSON-like structure
    json_candidates = _extract_balanced_json_candidates(normalized)
    for candidate in json_candidates:
        if _looks_like_json(candidate):
            return _normalize_json_formatting(candidate)
    
    # Pattern 4: If no code blocks or clear JSON structure, try the whole response
    # Remove common prefixes/suffixes that might interfere
    cleaned_full = _remove_common_prefixes_suffixes(normalized)
    if _looks_like_json(cleaned_full):
        return _normalize_json_formatting(cleaned_full)
    
    # If all extraction attempts fail, raise an error
    raise ValueError("No valid JSON structure found in LLM response")


def _looks_like_json(text: str) -> bool:
    """Check if text looks like it could be valid JSON.
    
    Args:
        text: Text to check
        
    Returns:
        bool: True if text appears to be JSON-like
    """
    text = text.strip()
    if not text:
        return False
    
    # Must start and end with braces for object
    if not (text.startswith('{') and text.endswith('}')):
        return False
    
    # Should contain both required fields
    if '"query"' not in text or '"papers"' not in text:
        return False
    
    # Basic structure check - should have reasonable JSON-like content
    if text.count('{') < 1 or text.count('}') < 1:
        return False
    
    return True


def _extract_balanced_json_candidates(text: str) -> List[str]:
    """Extract potential JSON candidates by finding balanced brace structures.
    
    Args:
        text: Text to search for JSON structures
        
    Returns:
        List[str]: List of potential JSON candidates, ordered by size (largest first)
    """
    candidates = []
    
    # Find all opening braces and try to match them with closing braces
    for i, char in enumerate(text):
        if char == '{':
            brace_count = 0
            for j in range(i, len(text)):
                if text[j] == '{':
                    brace_count += 1
                elif text[j] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found a balanced structure
                        candidate = text[i:j+1].strip()
                        if len(candidate) > 10:  # Minimum reasonable JSON size
                            candidates.append(candidate)
                        break
    
    # Sort by length (largest first) to prioritize more complete structures
    return sorted(candidates, key=len, reverse=True)


def _remove_common_prefixes_suffixes(text: str) -> str:
    """Remove common prefixes and suffixes that might interfere with JSON parsing.
    
    Args:
        text: Text to clean
        
    Returns:
        str: Cleaned text
    """
    # Common prefixes to remove
    prefixes = [
        r'^.*?(?=\{)',  # Everything before the first opening brace
        r'^[^{]*',      # Non-brace characters at the start
    ]
    
    # Common suffixes to remove  
    suffixes = [
        r'\}.*?$',      # Everything after the last closing brace (keep the brace)
        r'[^}]*$',      # Non-brace characters at the end
    ]
    
    cleaned = text
    
    # Apply prefix removal
    for prefix in prefixes:
        cleaned = re.sub(prefix, '', cleaned, count=1)
    
    # Apply suffix removal (but keep the closing brace)
    # Find the last closing brace and remove everything after it
    last_brace = cleaned.rfind('}')
    if last_brace != -1:
        cleaned = cleaned[:last_brace + 1]
    
    return cleaned.strip()


def _normalize_json_formatting(json_str: str) -> str:
    """Normalize JSON formatting for consistent parsing.
    
    Args:
        json_str: JSON string to normalize
        
    Returns:
        str: Normalized JSON string
    """
    # Remove extra whitespace while preserving string content
    # This is a simple normalization - for more complex cases, 
    # we could parse and re-serialize, but that might fail on malformed JSON
    
    # Normalize line endings
    normalized = re.sub(r'\r\n|\r', '\n', json_str)
    
    # CRITICAL FIX: Handle literal newlines within JSON string values
    # This fixes the "Invalid control character" error when LLMs insert
    # literal newlines within JSON strings instead of proper escaping
    normalized = _fix_newlines_in_json_strings(normalized)
    
    # Remove excessive whitespace around structural elements
    # But be careful not to modify string content
    normalized = re.sub(r'\s*{\s*', '{', normalized)
    normalized = re.sub(r'\s*}\s*', '}', normalized)
    normalized = re.sub(r'\s*\[\s*', '[', normalized)
    normalized = re.sub(r'\s*\]\s*', ']', normalized)
    normalized = re.sub(r'\s*,\s*', ',', normalized)
    normalized = re.sub(r'\s*:\s*', ':', normalized)
    
    # Remove leading/trailing whitespace
    return normalized.strip()


def _fix_newlines_in_json_strings(json_str: str) -> str:
    """Fix literal newlines within JSON string values.
    
    This function identifies JSON string values that contain literal newlines
    and either removes them (joining the lines) or escapes them properly.
    This fixes the "Invalid control character" JSON parsing error.
    
    Args:
        json_str: JSON string that may contain literal newlines in string values
        
    Returns:
        str: JSON string with fixed newlines in string values
    """
    result = []
    i = 0
    in_string = False
    escape_next = False
    
    while i < len(json_str):
        char = json_str[i]
        
        if escape_next:
            # Previous character was a backslash, so this character is escaped
            result.append(char)
            escape_next = False
        elif char == '\\' and in_string:
            # This is an escape character
            result.append(char)
            escape_next = True
        elif char == '"' and not escape_next:
            # This is a quote that starts or ends a string
            result.append(char)
            in_string = not in_string
        elif char == '\n' and in_string:
            # This is a literal newline within a JSON string - remove it
            # and join with the next line (removing any leading whitespace)
            # Skip the newline and any following whitespace
            i += 1
            while i < len(json_str) and json_str[i] in ' \t':
                i += 1
            # Continue without adding anything (effectively removes the newline and whitespace)
            continue
        else:
            # Regular character
            result.append(char)
        
        i += 1
    
    return ''.join(result)
