# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - JSON Parsing Failure Handling
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For deterministic bugs, scope the property to the concrete failing case(s) to ensure reproducibility
  - Test that malformed JSON responses (syntax errors, missing fields, invalid types) are handled gracefully without crashing
  - Test cases: trailing commas, missing "query"/"papers" fields, non-list "papers", conversational text responses
  - The test assertions should match the Expected Behavior Properties from design (display error message, show raw response, continue operation)
  - Run test on UNFIXED code in `src/retrieval/orchestrator.py`
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found to understand root cause (JSON parsing exceptions, application crashes)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Valid JSON Response Processing
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for valid JSON responses (well-formed JSON, code block wrapped JSON)
  - Observe behavior for network errors and no-results scenarios
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code in `src/retrieval/orchestrator.py`
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix for JSON parsing error handling

  - [x] 3.1 Implement enhanced JSON extraction and response cleaning
    - Improve regex-based cleaning to handle multiple code block formats (```json, ```, etc.)
    - Handle mixed content with JSON embedded in text
    - Add robust whitespace and formatting normalization
    - Support various LLM response patterns and edge cases
    - _Bug_Condition: isBugCondition(input) where NOT isValidJSON(input.cleaned_output) OR NOT hasRequiredFields(input.parsed_json, ["query", "papers"]) OR NOT isValidStructure(input.parsed_json)_
    - _Expected_Behavior: Display meaningful error message, show raw LLM response, continue operation without crashing_
    - _Preservation: Valid JSON responses continue to parse successfully, code block extraction preserved_
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2_

  - [x] 3.2 Implement layered error handling for different failure types
    - Add specific error handling for JSON syntax errors with detailed messages
    - Add schema validation error handling with field-specific feedback
    - Implement fallback mechanisms for partial data recovery
    - Ensure application continues running after any parsing failure
    - _Bug_Condition: JSON parsing fails due to syntax errors, missing fields, or invalid structure_
    - _Expected_Behavior: Graceful error handling with specific error messages and continued operation_
    - _Preservation: Existing error handling for network issues and no-results preserved_
    - _Requirements: 1.1, 1.2, 1.4, 2.1, 2.2, 2.4, 3.3, 3.4_

  - [x] 3.3 Enhance error reporting and debugging information
    - Display specific error types with actionable messages using MessageFormatter
    - Always show raw LLM response for troubleshooting when parsing fails
    - Maintain user-friendly error messages without exposing internal details
    - Add structured error information for better debugging
    - _Bug_Condition: JSON parsing errors occur without sufficient debugging information_
    - _Expected_Behavior: Clear error messages with raw response display for debugging_
    - _Preservation: Existing MessageFormatter functionality and error display patterns preserved_
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3_

  - [x] 3.4 Add comprehensive validation with graceful degradation
    - Validate required fields ("query", "papers") with specific error messages
    - Check data types and structure integrity before model validation
    - Provide clear feedback for each type of validation failure
    - Ensure ResearchReport.model_validate is only called with valid structure
    - _Bug_Condition: Invalid JSON structure causes validation failures and crashes_
    - _Expected_Behavior: Comprehensive validation with graceful error handling_
    - _Preservation: Successful validation and report generation for valid inputs preserved_
    - _Requirements: 1.2, 2.2, 3.1_

  - [x] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - JSON Parsing Failure Handling
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Valid JSON Response Processing
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions in valid JSON handling, network errors, no-results)

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.