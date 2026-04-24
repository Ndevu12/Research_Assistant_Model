# JSON Parsing Error Fix Bugfix Design

## Overview

The AI Research Assistant application crashes when LLM responses contain malformed JSON, preventing users from continuing their research workflow. This design implements robust error handling that gracefully manages JSON parsing failures while preserving all existing functionality for valid responses. The fix focuses on the `run_research_helper` function in `src/retrieval/orchestrator.py` where JSON parsing occurs without proper error recovery.

## Glossary

- **Bug_Condition (C)**: The condition that triggers JSON parsing failures - when LLM responses contain malformed JSON, missing required fields, or non-JSON content
- **Property (P)**: The desired behavior when JSON parsing fails - display meaningful error messages and continue operation instead of crashing
- **Preservation**: Existing functionality for valid JSON responses, network error handling, and no-results scenarios that must remain unchanged
- **run_research_helper**: The function in `src/retrieval/orchestrator.py` that orchestrates paper retrieval and LLM analysis
- **analysis_agent**: The Pydantic AI agent that processes paper data and returns JSON responses
- **ResearchReport**: The Pydantic model that validates the expected JSON structure with "query" and "papers" fields

## Bug Details

### Bug Condition

The bug manifests when the LLM returns responses that cannot be successfully parsed as valid JSON or do not conform to the expected ResearchReport schema. The `run_research_helper` function attempts to parse LLM output without comprehensive error handling, causing application crashes.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type LLMResponse (string)
  OUTPUT: boolean
  
  RETURN (NOT isValidJSON(input.cleaned_output) 
         OR NOT hasRequiredFields(input.parsed_json, ["query", "papers"])
         OR NOT isValidStructure(input.parsed_json))
         AND parsingAttempted(input)
END FUNCTION
```

### Examples

- **Malformed JSON Syntax**: LLM returns `{"query": "AI research", "papers": [{"title": "Paper 1", "key_points": ["point 1",]}]}` (trailing comma causes syntax error)
- **Missing Required Fields**: LLM returns `{"papers": [{"title": "Paper 1"}]}` (missing "query" field)
- **Invalid Field Types**: LLM returns `{"query": "AI research", "papers": "not a list"}` ("papers" should be a list)
- **Non-JSON Response**: LLM returns conversational text like "I found these papers for you: Paper 1, Paper 2"

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Valid JSON responses with correct structure must continue to parse and display research reports successfully
- Valid JSON wrapped in code blocks must continue to be extracted and parsed correctly
- Network error handling during paper retrieval must remain unchanged
- No-results scenarios must continue to display appropriate messages

**Scope:**
All inputs that do NOT involve JSON parsing failures should be completely unaffected by this fix. This includes:
- Well-formed JSON responses from the LLM
- Network connectivity issues during paper retrieval
- Empty search results from paper databases
- User input validation and interactive mode functionality

## Hypothesized Root Cause

Based on the bug description and code analysis, the most likely issues are:

1. **Insufficient Error Handling**: The current JSON parsing logic uses a simple try-catch that doesn't differentiate between different types of parsing failures
   - Syntax errors in JSON structure
   - Missing required fields after successful JSON parsing
   - Invalid data types in parsed JSON

2. **Inadequate Response Cleaning**: The regex-based cleaning may not handle all LLM response variations
   - Multiple code block formats
   - Mixed content with JSON embedded in text
   - Inconsistent whitespace or formatting

3. **Rigid Validation Logic**: The current validation expects perfect schema compliance without fallback mechanisms
   - No graceful degradation for partial data
   - No retry mechanisms for recoverable errors

4. **Poor Error Reporting**: Current error messages don't provide sufficient context for debugging
   - Generic parsing error messages
   - No display of raw LLM response for troubleshooting

## Correctness Properties

Property 1: Bug Condition - Graceful JSON Parsing Error Handling

_For any_ LLM response where JSON parsing fails (isBugCondition returns true), the fixed function SHALL display a meaningful error message, show the raw LLM response for debugging, and continue operation without crashing the application.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation - Valid JSON Response Processing

_For any_ LLM response where JSON parsing succeeds (isBugCondition returns false), the fixed function SHALL produce exactly the same behavior as the original function, preserving successful research report generation and display.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `src/retrieval/orchestrator.py`

**Function**: `run_research_helper`

**Specific Changes**:
1. **Enhanced JSON Extraction**: Improve the regex-based cleaning to handle more LLM response variations
   - Support multiple code block formats (```json, ```, etc.)
   - Handle mixed content with embedded JSON
   - Robust whitespace and formatting normalization

2. **Layered Error Handling**: Implement specific error handling for different failure types
   - JSON syntax errors with detailed error messages
   - Schema validation errors with field-specific feedback
   - Fallback mechanisms for partial data recovery

3. **Improved Error Reporting**: Enhance error messages and debugging information
   - Specific error types with actionable messages
   - Always display raw LLM response for troubleshooting
   - Maintain application flow after errors

4. **Response Validation Enhancement**: Add comprehensive validation with graceful degradation
   - Validate required fields with specific error messages
   - Check data types and structure integrity
   - Provide fallback behavior for recoverable issues

5. **Logging and Debugging**: Add structured logging for better error tracking
   - Log parsing attempts and failures
   - Track error patterns for future improvements
   - Maintain debugging information without exposing to users

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate various malformed LLM responses and assert that the application handles them gracefully. Run these tests on the UNFIXED code to observe failures and understand the root cause.

**Test Cases**:
1. **Malformed JSON Syntax Test**: Simulate LLM response with trailing commas, missing brackets (will fail on unfixed code)
2. **Missing Required Fields Test**: Simulate LLM response with valid JSON but missing "query" or "papers" fields (will fail on unfixed code)
3. **Invalid Data Types Test**: Simulate LLM response where "papers" is not a list or contains invalid objects (will fail on unfixed code)
4. **Non-JSON Response Test**: Simulate LLM response with conversational text instead of JSON (will fail on unfixed code)

**Expected Counterexamples**:
- Application crashes with JSON parsing exceptions
- Possible causes: insufficient error handling, rigid validation, poor response cleaning

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := run_research_helper_fixed(input)
  ASSERT gracefulErrorHandling(result)
  ASSERT applicationContinuesRunning(result)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT run_research_helper_original(input) = run_research_helper_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for valid JSON responses, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Valid JSON Preservation**: Observe that well-formed JSON responses work correctly on unfixed code, then write test to verify this continues after fix
2. **Code Block Extraction Preservation**: Observe that JSON wrapped in code blocks works correctly on unfixed code, then write test to verify this continues after fix
3. **Network Error Preservation**: Observe that network errors are handled correctly on unfixed code, then write test to verify this continues after fix

### Unit Tests

- Test JSON extraction with various code block formats and mixed content
- Test error handling for specific JSON syntax errors and validation failures
- Test that error messages are meaningful and include raw response data

### Property-Based Tests

- Generate random malformed JSON responses to verify graceful error handling across many scenarios
- Generate random valid JSON structures to verify preservation of successful parsing behavior
- Test that all error conditions result in continued application operation rather than crashes

### Integration Tests

- Test full research workflow with malformed LLM responses in interactive mode
- Test that users can submit new queries after JSON parsing failures
- Test that error messages provide sufficient information for debugging without exposing internal details