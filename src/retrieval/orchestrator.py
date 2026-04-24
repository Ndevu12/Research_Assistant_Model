# -*- coding: utf-8 -*-
"""Orchestrator function for the retrieval module."""

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Optional

import aiohttp
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .helpers import _dedupe
from .models import PaperAnalysis, ResearchReport, RetrievedPaper
from .openalex import search_openalex
from .rendering import render_markdown
from .semanticscholar import search_semantic_scholar
from ..utils.message_formatter import MessageFormatter


@dataclass
class ValidationResult:
    """Result of JSON structure validation."""
    is_valid: bool
    error_message: str = ""
    error_type: str = ""
    show_raw_response: bool = True


def _validate_json_structure(parsed_data: any) -> ValidationResult:
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


# Run setup if Ollama is not available
try:
    import subprocess
    import sys
    subprocess.run(["ollama", "list"], capture_output=True, check=True, timeout=5)
except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
    print("Ollama not found. Running setup...")
    subprocess.run([sys.executable, "setup/run_setup.py"], check=True)

# Model configuration
provider = OpenAIProvider(base_url="http://localhost:11434/v1", api_key="ollama")
model_name = "llama3.2:3b"
model = OpenAIChatModel(model_name=model_name, provider=provider)

analysis_agent = Agent(
    model=model,
    system_prompt=(
        "You are a research assistant. "
        "You MUST respond with a JSON object that has exactly two keys: "
        '"query" (the user query string) and "papers" (a list of paper analysis objects). '
        'Each paper object must have: "title", "year" (optional int), "venue" (optional string), '
        '"url" (optional string), "doi" (optional string), "key_points" (list of strings), '
        '"why_relevant" (list of strings). '
        "Do not include any other fields or use a different structure. "
        "Do not include conversational filler."
    ),
)


def _extract_and_clean_json(raw_output: str) -> str:
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


def _extract_balanced_json_candidates(text: str) -> list[str]:
    """Extract potential JSON candidates by finding balanced brace structures.
    
    Args:
        text: Text to search for JSON structures
        
    Returns:
        list[str]: List of potential JSON candidates, ordered by size (largest first)
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


def _attempt_partial_recovery(raw_output: str, cleaned_output: str, parsed_data: dict = None) -> None:
    """Attempt to recover partial data from malformed JSON responses.
    
    This function tries to extract useful information even when the JSON
    structure is incomplete or malformed, providing fallback mechanisms
    for partial data recovery.
    
    Args:
        raw_output: The original raw LLM response
        cleaned_output: The cleaned JSON string that failed parsing
        parsed_data: Already parsed JSON data (if available)
    """
    try:
        print(MessageFormatter.partial_recovery_header())
        recovered_items = []
        
        # If we have parsed data, use it directly
        if parsed_data:
            if "query" in parsed_data:
                print(f"Recovered query: {parsed_data['query']}")
                recovered_items.append("query")
            
            if "papers" in parsed_data and isinstance(parsed_data["papers"], list):
                print(f"Found {len(parsed_data['papers'])} papers:")
                for i, paper in enumerate(parsed_data["papers"][:5], 1):  # Limit to first 5
                    if isinstance(paper, dict) and "title" in paper:
                        print(f"  {i}. {paper['title']}")
                recovered_items.append(f"{len(parsed_data['papers'])} papers")
            elif "papers" in parsed_data:
                print(f"Papers field found but not in expected format: {type(parsed_data['papers'])}")
                recovered_items.append("papers field (invalid format)")
        else:
            # Try to extract at least the query if it exists
            query_match = re.search(r'"query"\s*:\s*"([^"]*)"', cleaned_output)
            if query_match:
                query = query_match.group(1)
                print(f"Recovered query: {query}")
                recovered_items.append("query")
            
            # Try to extract paper titles if they exist
            title_matches = re.findall(r'"title"\s*:\s*"([^"]*)"', cleaned_output)
            if title_matches:
                print(f"Found {len(title_matches)} paper titles:")
                for i, title in enumerate(title_matches[:5], 1):  # Limit to first 5
                    print(f"  {i}. {title}")
                recovered_items.append(f"{len(title_matches)} paper titles")
        
        if recovered_items:
            print(MessageFormatter.recovery_success_message(recovered_items))
        else:
            print(MessageFormatter.recovery_failure_message())
            print(MessageFormatter.raw_response_header())
            print(raw_output)
        
    except Exception:
        # If partial recovery fails, just show the raw response
        print(MessageFormatter.recovery_failure_message())
        print(MessageFormatter.raw_response_header())
        print(raw_output)


async def run_research_helper(user_text: str, k_each: int = 8) -> None:
    """Run the research helper with papers from multiple sources."""
    async with aiohttp.ClientSession() as session:
        try:
            openalex_papers, s2_papers = await asyncio.gather(
                search_openalex(session, user_text, per_page=k_each),
                search_semantic_scholar(session, user_text, limit=k_each),
            )
        except Exception as e:
            print(MessageFormatter.network_error(str(e)))
            return

    top = _dedupe(openalex_papers + s2_papers)[:10]

    if not top:
        print(MessageFormatter.no_results_message())
        return

    payload_items = [
        {
            "title": p.title,
            "abstract": p.abstract[:500] if p.abstract else "No abstract provided.",
            "url": p.url or p.doi,
        }
        for p in top
    ]

    # Properly serialize payload_items to JSON to ensure proper escaping
    payload_json = json.dumps(payload_items, ensure_ascii=False)

    prompt = (
        f"User Query: {user_text}\n\n"
        f"Analyze these papers and return ONLY a JSON object.\n"
        f"Data: {payload_json}"
    )

    result = await analysis_agent.run(prompt)

    try:
        raw_output = result.output
        clean_json = _extract_and_clean_json(raw_output)
        parsed = json.loads(clean_json)
        
        # Comprehensive validation with graceful degradation
        validation_result = _validate_json_structure(parsed)
        if not validation_result.is_valid:
            # Handle validation failure with specific error message
            print(validation_result.error_message)
            print(MessageFormatter.debugging_suggestion(validation_result.error_type))
            if validation_result.show_raw_response:
                print(MessageFormatter.raw_response_header())
                print(raw_output)
            return
        
        # Only call ResearchReport.model_validate with validated structure
        report = ResearchReport.model_validate(parsed)
        print(render_markdown(report))
    except json.JSONDecodeError as e:
        # Specific handling for JSON syntax errors
        print(MessageFormatter.json_syntax_error(str(e), e.lineno, e.colno))
        print(MessageFormatter.debugging_suggestion("syntax"))
        print(MessageFormatter.raw_response_header())
        print(result.output)
    except ValueError as extraction_error:
        # Handle JSON extraction failures (from _extract_and_clean_json)
        if "No valid JSON structure found" in str(extraction_error):
            print(MessageFormatter.extraction_error(str(extraction_error)))
            print(MessageFormatter.debugging_suggestion("extraction"))
            print(MessageFormatter.raw_response_header())
            print(result.output)
            return
        
        # Handle other ValueError cases (structure validation)
        error_msg = str(extraction_error)
        if "Missing required fields" in error_msg:
            # Specific handling for schema validation errors
            print(MessageFormatter.schema_validation_error(error_msg))
            print(MessageFormatter.debugging_suggestion("schema"))
            # Attempt partial data recovery
            try:
                parsed_for_recovery = json.loads(clean_json)
                _attempt_partial_recovery(result.output, clean_json, parsed_for_recovery)
            except:
                print(MessageFormatter.raw_response_header())
                print(result.output)
        elif "Expected JSON object" in error_msg:
            print(MessageFormatter.structure_error("Response is not a JSON object"))
            print(MessageFormatter.debugging_suggestion("structure"))
            print(MessageFormatter.raw_response_header())
            print(result.output)
        elif "'papers' must be a list" in error_msg:
            print(MessageFormatter.field_type_error("papers", "list", type(parsed.get("papers", None)).__name__))
            print(MessageFormatter.debugging_suggestion("field_type"))
            print(MessageFormatter.raw_response_header())
            print(result.output)
        else:
            # Generic validation error
            print(MessageFormatter.validation_error(error_msg))
            print(MessageFormatter.debugging_suggestion("validation"))
            print(MessageFormatter.raw_response_header())
            print(result.output)
    except Exception as e:
        # Handle Pydantic validation errors and other exceptions
        error_msg = str(e)
        if "validation error" in error_msg.lower():
            print(MessageFormatter.validation_error(error_msg))
            print(MessageFormatter.debugging_suggestion("validation"))
        else:
            print(MessageFormatter.parsing_error(error_msg))
            print(MessageFormatter.debugging_suggestion("validation"))
        print(MessageFormatter.raw_response_header())
        print(result.output)
