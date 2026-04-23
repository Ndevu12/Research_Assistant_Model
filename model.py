# -*- coding: utf-8 -*-
"""AI Research Assistant Model

Run setup first with:
    python setup/run_setup.py

Then run the assistant:
    python model.py
"""

import asyncio
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import aiohttp
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# Run setup if Ollama is not available
try:
    subprocess.run(["ollama", "list"], capture_output=True, check=True, timeout=5)
except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
    print("Ollama not found. Running setup...")
    subprocess.run([sys.executable, "setup/run_setup.py"], check=True)


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

provider = OpenAIProvider(base_url="http://localhost:11434/v1", api_key="ollama")
model_name = "llama3.2:3b"
model = OpenAIChatModel(model_name=model_name, provider=provider)

# ---------------------------------------------------------------------------
# Data schemas
# ---------------------------------------------------------------------------

class PaperAnalysis(BaseModel):
    title: str
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    why_relevant: List[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    query: str
    papers: List[PaperAnalysis]


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

# ---------------------------------------------------------------------------
# Retrieval helpers
# ---------------------------------------------------------------------------

@dataclass
class RetrievedPaper:
    title: str
    abstract: Optional[str]
    year: Optional[int]
    venue: Optional[str]
    url: Optional[str]
    doi: Optional[str]
    source: str


def _normalize_title(t: str) -> str:
    t = t.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", "", t)
    return t


def _dedupe(papers: List[RetrievedPaper]) -> List[RetrievedPaper]:
    seen: set[Tuple[Optional[str], str]] = set()
    out: List[RetrievedPaper] = []
    for p in papers:
        key = (p.doi.lower().strip() if p.doi else None, _normalize_title(p.title))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _openalex_abstract_from_inverted_index(inv: Optional[Dict[str, List[int]]]) -> Optional[str]:
    if not inv:
        return None
    positions: Dict[int, str] = {}
    for word, pos_list in inv.items():
        for pos in pos_list:
            positions[pos] = word
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions.keys()))


async def search_openalex(session: aiohttp.ClientSession, query: str, per_page: int = 8) -> List[RetrievedPaper]:
    url = "https://api.openalex.org/works"
    params = {"search": query, "per-page": str(per_page)}

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with session.get(url, params=params, timeout=60) as r:
                r.raise_for_status()
                data = await r.json()
                break
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            print(f"OpenAlex attempt {attempt + 1} failed: {e}. Retrying...")
            await asyncio.sleep(2 ** attempt)

    results = []
    for item in data.get("results", []):
        title = item.get("display_name") or "Untitled"
        year = item.get("publication_year")
        doi = item.get("doi")
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        venue = source.get("display_name") or item.get("host_venue", {}).get("display_name")
        abstract = _openalex_abstract_from_inverted_index(item.get("abstract_inverted_index"))
        url_out = item.get("id") or item.get("primary_location", {}).get("landing_page_url")
        results.append(RetrievedPaper(title=title, abstract=abstract, year=year,
                                      venue=venue, url=url_out, doi=doi, source="openalex"))
    return results


async def search_semantic_scholar(session: aiohttp.ClientSession, query: str, limit: int = 8) -> List[RetrievedPaper]:
    url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    params = {"query": query, "limit": str(limit), "fields": "title,abstract,year,venue,url,externalIds"}
    headers = {}
    s2_key = os.getenv("S2_API_KEY")
    if s2_key:
        headers["x-api-key"] = s2_key

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with session.get(url, params=params, headers=headers, timeout=60) as r:
                if r.status == 429:
                    retry_after = r.headers.get("Retry-After", "60")
                    print(f"Semantic Scholar rate limited. Waiting {retry_after}s...")
                    await asyncio.sleep(int(retry_after))
                    continue
                r.raise_for_status()
                data = await r.json()
                break
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            print(f"Semantic Scholar attempt {attempt + 1} failed: {e}. Retrying...")
            await asyncio.sleep(2 ** attempt)
    else:
        print("Semantic Scholar: Max retries exceeded. Skipping this source.")
        return []

    results = []
    for item in data.get("data", []) or []:
        external = item.get("externalIds") or {}
        doi = external.get("DOI")
        results.append(RetrievedPaper(
            title=item.get("title") or "Untitled",
            abstract=item.get("abstract"),
            year=item.get("year"),
            venue=item.get("venue"),
            url=item.get("url"),
            doi=(f"https://doi.org/{doi}" if doi and not str(doi).startswith("http") else doi),
            source="semanticscholar",
        ))
    return results

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_markdown(report: ResearchReport) -> str:
    lines = [f"# Research helper results\n", f"Query: {report.query}\n"]
    for i, p in enumerate(report.papers, start=1):
        meta = [str(p.year) if p.year else "", p.venue or ""]
        meta_str = " | ".join(m for m in meta if m)
        lines.append(f"## {i}. {p.title}")
        if meta_str:
            lines.append(meta_str)
        if p.url:
            lines.append(f"Source: {p.url}")
        elif p.doi:
            lines.append(f"Source: {p.doi}")
        else:
            lines.append("Source: (not provided)")
        if p.key_points:
            lines.append("\nKey points:")
            lines.extend(f"- {b}" for b in p.key_points)
        if p.why_relevant:
            lines.append("\nWhy this matches your query:")
            lines.extend(f"- {b}" for b in p.why_relevant)
        lines.append("\n")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def run_research_helper(user_text: str, k_each: int = 8) -> None:
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    QUERY = "On-device LLM reasoning for IoT DDoS detection"
    asyncio.run(run_research_helper(QUERY))
