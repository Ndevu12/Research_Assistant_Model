# -*- coding: utf-8 -*-
"""AI Research Assistant - Main Entry Point

Run with:
    python -m src
    python -m src "your query"
    python -m src --help
"""

import argparse
import asyncio
import sys
from pathlib import Path

from .retrieval.orchestrator import run_research_helper
from .utils.input_handler import get_user_query
from .utils.message_formatter import MessageFormatter
from .utils.logging_system import logger


def ensure_setup() -> bool:
    """Ensure all setup requirements are met before running the application.
    
    Returns:
        bool: True if setup is complete and successful, False otherwise
    """
    # Add setups to path - use absolute path from current working directory
    import os
    cwd = Path(os.getcwd())
    setups_path = cwd / "setups"
    
    if not setups_path.exists():
        logger.error(f"Setup directory not found at {setups_path}")
        return False
    
    if str(setups_path) not in sys.path:
        sys.path.insert(0, str(setups_path))
    
    try:
        # Import setup modules
        import health_check
        import manager
    except ImportError as e:
        logger.error(f"Failed to import setup modules: {e}")
        return False
    
    # Check current setup status
    logger.info("Checking setup status...")
    is_running, message = health_check.check_ollama_running()
    if is_running:
        logger.info("Setup is complete and ready to use")
        return True
    
    # Setup is incomplete, run full setup
    logger.warning("Setup incomplete. Running automatic setup...")
    health_check.print_report()
    
    if not manager.run_setup():
        logger.error("Automatic setup failed. Please run setup manually: python -m setups.manager")
        return False
    
    logger.info("Setup completed successfully!")
    return True


def run_interactive_mode() -> None:
    """Run the research assistant in interactive mode.
    
    Displays welcome message, prompts for queries in a loop, processes each query,
    and exits gracefully when the user enters an exit command or sends Ctrl+C.
    
    Requirements:
        - 1.1: Enter interactive mode when no query argument provided
        - 1.3: Process user-entered queries
        - 2.1: Prompt for another query after processing
        - 2.2: Process each query independently
        - 2.3: Maintain session until explicit exit
        - 2.4: Display separator between query results
        - 5.1: Display welcome message
        - 5.2: Include query entry instructions
        - 5.3: Include exit instructions
        - 3.4: Display farewell message on exit
    """
    # Display welcome message
    print(MessageFormatter.welcome_message())
    
    try:
        while True:
            # Get user query
            query = get_user_query()
            
            # Check for exit condition
            if query is None:
                break
            
            # Process the query
            asyncio.run(run_research_helper(query))
            
            # Display separator between results
            print(MessageFormatter.result_separator())
    
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print()  # New line after ^C
    
    finally:
        # Display farewell message
        print(MessageFormatter.farewell_message())


def main() -> None:
    """Main entry point for the CLI.
    
    Ensures setup is complete, then detects operating mode based on query argument:
    - If query provided: runs in batch mode (existing behavior)
    - If no query: runs in interactive mode
    
    Requirements:
        - 1.1: Enter interactive mode when no query argument provided
        - 1.4: Preserve backward compatibility with batch mode
    """
    # Ensure setup is complete before proceeding
    if not ensure_setup():
        logger.error("Cannot proceed without completing setup")
        sys.exit(1)
    
    parser = argparse.ArgumentParser(
        description="AI Research Assistant - Retrieve and analyze academic papers"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Research query. If omitted, enters interactive mode where you can submit multiple queries."
    )
    args = parser.parse_args()
    
    # Detect mode based on query argument
    if args.query:
        # Batch mode: run single query and exit
        asyncio.run(run_research_helper(args.query))
    else:
        # Interactive mode: prompt for queries in a loop
        run_interactive_mode()


if __name__ == "__main__":
    main()
