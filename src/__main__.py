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


async def run_research_helper(user_text: str, k_each: int = 8) -> None:
    """Run the research workflow with the given query."""
    async with aiohttp.ClientSession() as session:
        try:
            openalex_papers, s2_papers = await asyncio.gather(
                search_openalex(session, user_text, per_page=k_each),
                search_semantic_scholar(session, user_text, limit=k_each),
            )
        except Exception as e:
            print(f"Error fetching papers: {e}")
            print("Check your internet connection and try again.")
            return

    top = _dedupe(openalex_papers + s2_papers)[:10]

    if not top:
        print("No papers found. Try a different query.")
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
        print(f"❌ Parsing Error: {e}")
        print("-- RAW RESPONSE FROM LLM --")
        print(result.output)


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="AI Research Assistant - Retrieve and analyze academic papers"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="On-device LLM reasoning for IoT DDoS detection",
        help="Research query (default: On-device LLM reasoning for IoT DDoS detection)"
    )
    args = parser.parse_args()
    
    asyncio.run(run_research_helper(args.query))


if __name__ == "__main__":
    main()
