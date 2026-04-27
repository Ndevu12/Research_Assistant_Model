# -*- coding: utf-8 -*-
"""Recovery utilities for orchestrator."""

import re
from typing import Optional, List, Dict

from ...utils.message_formatter import MessageFormatter
from ...utils.response_models import RecoveryResult, RecoveryMethod, RecoveryConfig


def attempt_partial_recovery(raw_output: str, cleaned_output: str, parsed_data: dict = None) -> None:
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


def enhanced_partial_recovery(
    raw_output: str, 
    cleaned_output: str, 
    parsed_data: dict = None,
    recovery_config: Optional[RecoveryConfig] = None
) -> RecoveryResult:
    """Enhanced version of existing partial recovery with additional techniques.
    
    Extends the current attempt_partial_recovery with:
    - Systematic recovery result tracking
    - Additional extraction patterns
    - Configurable recovery methods
    - Structured return values
    
    Args:
        raw_output: The original raw LLM response
        cleaned_output: The cleaned JSON string that failed parsing
        parsed_data: Already parsed JSON data (if available)
        recovery_config: Configuration for recovery behavior
        
    Returns:
        RecoveryResult: Structured recovery result with success status and data
    """    
    # Use default config if none provided
    if recovery_config is None:
        recovery_config = RecoveryConfig()
    
    recovery_result = RecoveryResult()
    recovered_data = {}
    warnings = []
    
    try:
        # First, call existing recovery function to maintain current behavior
        attempt_partial_recovery(raw_output, cleaned_output, parsed_data)
        
        # Enhanced recovery techniques
        if recovery_config.enable_enhanced_extraction:
            enhanced_data = _extract_with_enhanced_patterns(raw_output)
            if enhanced_data:
                recovered_data.update(enhanced_data)
                recovery_result.recovery_method = RecoveryMethod.ENHANCED_PATTERNS
        
        # Try to recover from parsed_data if available
        if parsed_data:
            if "query" in parsed_data and isinstance(parsed_data["query"], str):
                recovered_data["query"] = parsed_data["query"]
            
            if "papers" in parsed_data:
                if isinstance(parsed_data["papers"], list):
                    # Filter out invalid papers and keep valid ones
                    valid_papers = []
                    for paper in parsed_data["papers"]:
                        if isinstance(paper, dict) and "title" in paper:
                            valid_papers.append(paper)
                    if valid_papers:
                        recovered_data["papers"] = valid_papers
                else:
                    warnings.append("Papers field is not a list")
        
        # Pattern-based recovery from cleaned output
        if not recovered_data.get("query"):
            query_patterns = [
                r'"query"\s*:\s*"([^"]*)"',
                r"'query'\s*:\s*'([^']*)'",
                r'query:\s*"([^"]*)"',
                r'Query:\s*([^\n,}]+)'
            ]
            for pattern in query_patterns:
                match = re.search(pattern, cleaned_output, re.IGNORECASE)
                if match:
                    recovered_data["query"] = match.group(1).strip()
                    break
        
        # Enhanced paper extraction
        if not recovered_data.get("papers"):
            papers = _extract_papers_with_patterns(cleaned_output)
            if papers:
                recovered_data["papers"] = papers
        
        # Set success status and confidence
        if recovered_data:
            recovery_result.success = True
            recovery_result.recovered_data = recovered_data
            recovery_result.warnings = warnings
            
            # Calculate confidence based on completeness
            confidence = 0.0
            if "query" in recovered_data:
                confidence += 0.3
            if "papers" in recovered_data:
                confidence += 0.7 * min(len(recovered_data["papers"]) / 3, 1.0)
            recovery_result.confidence_score = confidence
        else:
            recovery_result.success = False
            recovery_result.error_message = "No recoverable data found"
        
    except Exception as e:
        recovery_result.success = False
        recovery_result.error_message = str(e)
    
    return recovery_result


def _extract_with_enhanced_patterns(text: str) -> Optional[Dict]:
    """Additional extraction patterns beyond existing recovery.
    
    Args:
        text: Raw text to extract from
        
    Returns:
        dict: Extracted data or None if nothing found
    """
    extracted = {}
    
    # Enhanced patterns for paper extraction from conversational text
    paper_patterns = [
        # Pattern: "Title: Paper Name"
        r'(?:Title|Paper):\s*([^\n]+)',
        # Pattern: "1. Paper Name"
        r'^\s*\d+\.\s*([^\n]+)',
        # Pattern: "- Paper Name"
        r'^\s*[-*]\s*([^\n]+)',
    ]
    
    papers = []
    for pattern in paper_patterns:
        matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
        for match in matches:
            title = match.strip()
            if len(title) > 10 and not title.lower().startswith(('the', 'a ', 'an ')):
                papers.append({"title": title})
    
    if papers:
        extracted["papers"] = papers[:5]  # Limit to 5 papers
    
    # Try to extract query from conversational context
    query_patterns = [
        r'(?:looking for|searching for|find|about)\s+([^.!?]+)',
        r'(?:research on|papers on|studies on)\s+([^.!?]+)',
        r'(?:query|search):\s*([^.!?\n]+)'
    ]
    
    for pattern in query_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            if len(query) > 5:
                extracted["query"] = query
                break
    
    return extracted if extracted else None


def _extract_papers_with_patterns(text: str) -> List[Dict]:
    """Extract paper information using various patterns.
    
    Args:
        text: Text to extract papers from
        
    Returns:
        List[Dict]: List of extracted paper objects
    """
    papers = []
    
    # Try to find title patterns in the text
    title_patterns = [
        r'"title"\s*:\s*"([^"]+)"',
        r"'title'\s*:\s*'([^']+)'",
        r'title:\s*"([^"]+)"',
        r'Title:\s*([^\n,}]+)'
    ]
    
    for pattern in title_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            title = match.strip()
            if title and len(title) > 5:
                paper = {"title": title}
                
                # Try to find associated metadata near the title
                title_pos = text.find(match)
                context = text[max(0, title_pos-200):title_pos+200]
                
                # Look for year
                year_match = re.search(r'"year"\s*:\s*(\d{4})', context)
                if year_match:
                    paper["year"] = int(year_match.group(1))
                
                # Look for venue
                venue_match = re.search(r'"venue"\s*:\s*"([^"]+)"', context)
                if venue_match:
                    paper["venue"] = venue_match.group(1)
                
                papers.append(paper)
    
    return papers[:5]  # Limit to 5 papers
