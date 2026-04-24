# Implementation Plan: Interactive User Prompt System

## Overview

This implementation adds interactive query input capabilities to the AI Research Assistant. The system will support both batch mode (existing CLI argument-based queries) and interactive mode (prompt-based queries), allowing users to submit multiple queries in a single session and exit gracefully.

## Tasks

- [x] 1. Create input handling module
  - [x] 1.1 Create `src/utils/input_handler.py` module
    - Implement `get_user_query()` function to prompt for and validate user input
    - Handle empty input and whitespace-only input with error messages
    - Return stripped query string or None for exit commands
    - _Requirements: 1.3, 4.1, 4.2, 4.3_
  
  - [x] 1.2 Implement exit command detection
    - Detect "exit" and "quit" commands (case-insensitive)
    - Return None to signal exit condition
    - _Requirements: 3.1, 3.2_
  
  - [x] 1.3 Write unit tests for input handler
    - Test empty input handling
    - Test whitespace-only input handling
    - Test exit command detection
    - Test valid query input
    - _Requirements: 4.1, 4.2, 4.3, 3.1, 3.2_

- [x] 2. Implement interactive mode logic
  - [x] 2.1 Create interactive session loop in `src/__main__.py`
    - Implement `run_interactive_mode()` function with query loop
    - Call `get_user_query()` to get each query
    - Call `run_research_helper()` for each valid query
    - Break loop when user enters exit command
    - Display separator between query results
    - _Requirements: 1.1, 1.3, 2.1, 2.2, 2.3, 2.4_
  
  - [x] 2.2 Add welcome and farewell messages
    - Display welcome message with usage instructions on interactive mode start
    - Include instructions for entering queries and exiting
    - Display farewell message on exit
    - _Requirements: 5.1, 5.2, 5.3, 3.4_
  
  - [x] 2.3 Write integration tests for interactive mode
    - Test multi-query session flow
    - Test exit command handling
    - Test empty input re-prompting
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 4.2_

- [x] 3. Modify main entry point for mode detection
  - [x] 3.1 Update `main()` function to detect mode
    - Check if query argument is provided
    - If query provided: run batch mode (existing behavior)
    - If no query: run interactive mode
    - Preserve backward compatibility with existing CLI usage
    - _Requirements: 1.1, 1.4_
  
  - [x] 3.2 Update argument parser configuration
    - Make query argument optional (nargs="?")
    - Remove default query value
    - Update help text to reflect both modes
    - _Requirements: 1.1, 1.4_
  
  - [x] 3.3 Write unit tests for mode detection
    - Test batch mode with query argument
    - Test interactive mode without query argument
    - Test backward compatibility
    - _Requirements: 1.1, 1.4_

- [x] 4. Add interrupt signal handling
  - [x] 4.1 Implement Ctrl+C handler in interactive mode
    - Catch KeyboardInterrupt exception
    - Display farewell message on interrupt
    - Exit gracefully without stack trace
    - _Requirements: 3.3, 3.4, 3.5_
  
  - [x] 4.2 Write tests for signal handling
    - Test KeyboardInterrupt handling
    - Verify no error messages or stack traces on normal exit
    - _Requirements: 3.3, 3.5_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Update user interface messages
  - [x] 6.1 Implement consistent message formatting
    - Create message formatting utilities if needed
    - Ensure consistent prompt indicators
    - Apply consistent formatting to all user-facing messages
    - _Requirements: 5.4, 5.5_
  
  - [x] 6.2 Add clear input indicators
    - Display clear prompt for query input (e.g., "Enter your research query: ")
    - Display clear error messages for invalid input
    - _Requirements: 5.4_

- [x] 7. Final integration and testing
  - [x] 7.1 Test complete interactive workflow
    - Start system without arguments
    - Submit multiple queries
    - Test exit commands
    - Test Ctrl+C interrupt
    - Verify backward compatibility with batch mode
    - _Requirements: 1.1, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 1.4_
  
  - [x] 7.2 Verify all requirements are met
    - Review each acceptance criterion
    - Confirm all user stories are satisfied
    - _Requirements: All_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The implementation preserves backward compatibility with existing batch mode
- Interactive mode is triggered automatically when no query argument is provided
- All exit mechanisms (exit/quit commands and Ctrl+C) display farewell messages
- Empty input handling provides clear feedback and re-prompts the user
