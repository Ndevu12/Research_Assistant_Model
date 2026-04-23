# -*- coding: utf-8 -*-
"""Orchestrator function for the retrieval module."""

import asyncio
import json
import re

import aiohttp
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .helpers import _dedupe
from .models import PaperAnalysis, ResearchReport, RetrievedPaper
from .openalex import search_openalex
from .rendering import render_markdown
from .semanticscholar import search_semantic_scholar

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


async def run_research_helper(user_text: str, k_each: int = 8) -> None:
    """Run the research helper with papers from multiple sources."""
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
