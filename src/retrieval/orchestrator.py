# -*- coding: utf-8 -*-
"""Orchestrator function for the retrieval module."""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

import aiohttp

from .helpers import _dedupe
from .helpers_modules.json_extraction import extract_and_clean_json
from .helpers_modules.validation import validate_json_structure, enhance_validation_with_retry_strategy
from .helpers_modules.recovery import attempt_partial_recovery, enhanced_partial_recovery
from .models import PaperAnalysis, ResearchReport, RetrievedPaper
from .openalex import search_openalex
from .rendering import render_markdown
from .semanticscholar import search_semantic_scholar
from ..analysis.llm import analysis_agent
from ..utils.message_formatter import MessageFormatter
from ..utils.response_models import RecoveryConfig
from ..utils.logging_system import logger




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
        clean_json = extract_and_clean_json(raw_output)
        parsed_data = json.loads(clean_json)
        
        # Validate the parsed data
        validation_result = validate_json_structure(parsed_data)
        validation_result = enhance_validation_with_retry_strategy(validation_result)
        
        if not validation_result.is_valid:
            print(validation_result.error_message)
            if validation_result.show_raw_response:
                print(MessageFormatter.raw_response_header())
                print(raw_output)
                attempt_partial_recovery(raw_output, clean_json, parsed_data)
            return
        
        # Process the validated data
        research_report = ResearchReport(
            query=parsed_data["query"],
            papers=[
                PaperAnalysis(
                    title=p.get("title", ""),
                    year=p.get("year"),
                    venue=p.get("venue"),
                    url=p.get("url"),
                    doi=p.get("doi"),
                    key_points=p.get("key_points", []),
                    why_relevant=p.get("why_relevant", []),
                )
                for p in parsed_data.get("papers", [])
            ],
        )
        
        # Render the markdown output
        markdown_output = render_markdown(research_report)
        print(markdown_output)
        
    except json.JSONDecodeError as e:
        print(MessageFormatter.parsing_error(str(e)))
        print(MessageFormatter.raw_response_header())
        print(raw_output)
        attempt_partial_recovery(raw_output, clean_json, None)
    except ValueError as e:
        print(MessageFormatter.extraction_error(str(e)))
        print(MessageFormatter.raw_response_header())
        print(raw_output)
        attempt_partial_recovery(raw_output, "", None)
    except Exception as e:
        print(MessageFormatter.error_message(str(e)))
        print(MessageFormatter.raw_response_header())
        print(raw_output)
        attempt_partial_recovery(raw_output, "", None)
