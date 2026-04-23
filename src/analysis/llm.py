# -*- coding: utf-8 -*-
"""Analysis agent configuration for the analysis module."""

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


# Model configuration
provider = OpenAIProvider(base_url="http://localhost:11434/v1", api_key="ollama")
model_name = "llama3.2:3b"
model = OpenAIChatModel(model_name=model_name, provider=provider)


# Data schemas
class PaperAnalysis(BaseModel):
    """Analysis of a single paper."""
    title: str
    year: int | None = None
    venue: str | None = None
    url: str | None = None
    doi: str | None = None
    key_points: list[str] = Field(default_factory=list)
    why_relevant: list[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    """Complete research report with query and paper analyses."""
    query: str
    papers: list[PaperAnalysis]


# Analysis agent
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
