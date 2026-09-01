# -*- coding: utf-8 -*-
"""LLM provider abstraction and agent role definitions."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model

if TYPE_CHECKING:
    from ..config.settings import LLMConfig


class AgentRole(str, Enum):
    """Predefined agent roles with dedicated system prompts."""

    EXPANSION = "expansion"
    EXTRACTION = "extraction"
    SYNTHESIS = "synthesis"
    GAP_ANALYSIS = "gap_analysis"
    INTERACTIVE = "interactive"
    ANALYSIS = "analysis"


ROLE_SYSTEM_PROMPTS: dict[AgentRole, str] = {
    AgentRole.EXPANSION: (
        "You expand research queries. Respond with JSON only: "
        '{"variants": ["..."], "sub_questions": ["..."]}. '
        "Provide concise academic search phrases."
    ),
    AgentRole.EXTRACTION: (
        "You are a research paper analyst. "
        "Extract structured information from a single paper and respond with ONLY a JSON object "
        'with keys: "paper_id" (string), "title" (string), "methodology" (list of strings), '
        '"datasets" (list of strings), "benchmarks" (list of strings), '
        '"limitations" (list of strings), "findings" (list of strings), '
        '"evidence" (list of strings). '
        "When full-text passages are provided, evidence must contain short verbatim quotes "
        "from those passages that support the findings; otherwise leave evidence empty. "
        "Do not include conversational filler or markdown."
    ),
    AgentRole.SYNTHESIS: (
        "You are a research synthesis expert. "
        "Given structured extractions from multiple papers and thematic cluster summaries, "
        "produce cross-paper insights as ONLY a JSON object with keys: "
        '"agreements", "disagreements", "trends", "gaps", "datasets", "methodologies" '
        "(each a list of strings). Do not include conversational filler."
    ),
    AgentRole.GAP_ANALYSIS: (
        "You are a research strategist. "
        "Given cross-paper synthesis output, identify prioritized research gaps and opportunities. "
        "Respond with ONLY a JSON object with keys: "
        '"gaps" (list of strings), "opportunities" (list of strings), '
        '"underexplored_areas" (list of strings). '
        "Do not include conversational filler."
    ),
    AgentRole.INTERACTIVE: (
        "You are a research assistant helping refine literature review follow-up questions. "
        "Respond concisely and stay focused on the user's research topic."
    ),
    AgentRole.ANALYSIS: (
        "You are a research assistant. "
        "You MUST respond with a JSON object that has exactly two keys: "
        '"query" (the user query string) and "papers" (a list of paper analysis objects). '
        'Each paper object must have: "title", "year" (optional int), "venue" (optional string), '
        '"url" (optional string), "doi" (optional string), "key_points" (list of strings), '
        '"why_relevant" (list of strings). '
        "Do not include any other fields or use a different structure. "
        "Do not include conversational filler."
    ),
}


def normalize_openai_base_url(base_url: str) -> str:
    """Ensure an OpenAI-compatible base URL ends with ``/v1``."""
    normalized = base_url.rstrip("/")
    if not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    return normalized


def resolve_api_key(config: LLMConfig, env_var: str, default: str = "") -> str:
    """Resolve an API key from config or environment."""
    if config.api_key:
        return config.api_key
    return os.environ.get(env_var, default)


class LLMProvider(ABC):
    """Interface for LLM backends used by pydantic-ai agents."""

    name: ClassVar[str]

    @abstractmethod
    def create_model(self, config: LLMConfig) -> Model:
        """Create a pydantic-ai chat model from application settings."""

    async def complete(
        self,
        prompt: str,
        *,
        config: LLMConfig,
        system_prompt: str | None = None,
        schema: type[BaseModel] | None = None,
    ) -> str:
        """Run a single completion and return the model output text."""
        model = self.create_model(config)
        if schema is not None:
            structured_agent: Agent[None, BaseModel] = Agent(
                model=model,
                system_prompt=system_prompt or "",
                output_type=schema,
            )
            structured_result = await structured_agent.run(prompt)
            return structured_result.output.model_dump_json()
        agent = Agent(model=model, system_prompt=system_prompt or "")
        result = await agent.run(prompt)
        return str(result.output)
