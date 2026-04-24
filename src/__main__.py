# -*- coding: utf-8 -*-
"""AI Research Assistant - Main Entry Point

Run with:
    python -m src
    python -m src "your query"
    python -m src --help
"""

import argparse
import asyncio
import json
import re

import aiohttp

from .retrieval.models import ResearchReport
from .retrieval.openalex import search_openalex
from .retrieval.semanticscholar import search_semantic_scholar
from .retrieval.helpers import _dedupe
from .retrieval.rendering import render_markdown
from .analysis.llm import analysis_agent
from .utils.input_handler import get_user_query
from .utils.message_formatter import MessageFormatter


async def run_research_helper(user_text: str, k_each: int = 8) -> None:
    """Run the research workflow with the given query."""
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

    prompt = (
        f"User Query: {user_text}\n\n"
        f"Analyze these papers and return ONLY a JSON object.\n"
        f"Data: {payload_items}"
    )

    result = await analysis_agent.run(prompt)

    try:
        raw_output = result.output
        clean_json = re.sub(r"```json|```", "", raw_output).strip()
        parsed = json.loads(clean_json)
        
        # Handle case where LLM returns wrong structure
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object")
        if "query" not in parsed or "papers" not in parsed:
            raise ValueError(f"Missing required fields. Expected 'query' and 'papers', got: {list(parsed.keys())}")
        if not isinstance(parsed["papers"], list):
            raise ValueError("'papers' must be a list")
        
        report = ResearchReport.model_validate(parsed)
        print(render_markdown(report))
    except Exception as e:
        print(MessageFormatter.parsing_error(str(e)))
        print(MessageFormatter.raw_response_header())
        print(result.output)


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
    
    Detects operating mode based on query argument:
    - If query provided: runs in batch mode (existing behavior)
    - If no query: runs in interactive mode
    
    Requirements:
        - 1.1: Enter interactive mode when no query argument provided
        - 1.4: Preserve backward compatibility with batch mode
    """
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
