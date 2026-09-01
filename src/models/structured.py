# -*- coding: utf-8 -*-
"""Schema-enforced LLM calls via pydantic-ai structured outputs.

Instead of asking the model for JSON in prose and repairing whatever comes
back, the schema is attached to the agent (``output_type``) and pydantic-ai
enforces it natively — invalid output triggers the framework's own retry
with validation feedback, and the caller receives a typed object or an
exception. This replaces the string-repair path for providers that support
structured outputs; heuristic fallbacks remain the safety net.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model

from ..utils.logging_system import logger
from .base import ROLE_SYSTEM_PROMPTS, AgentRole
from .factory import AgentFactory, create_llm_provider

OutputT = TypeVar("OutputT", bound=BaseModel)

# Slim prompts for the structured path: the schema is enforced by the
# framework, so the "respond with ONLY JSON ..." scaffolding the legacy
# prompts carry is unnecessary and only adds noise.
STRUCTURED_ROLE_PROMPTS: dict[AgentRole, str] = {
    AgentRole.EXPANSION: (
        "You expand research queries into concise academic search phrases "
        "and focused sub-questions."
    ),
    AgentRole.EXTRACTION: (
        "You are a research paper analyst. Extract the paper's methodology, "
        "datasets, benchmarks, limitations, and findings. When full-text "
        "passages are provided, ground the extraction in them and quote short "
        "verbatim evidence snippets; otherwise leave evidence empty."
    ),
    AgentRole.SYNTHESIS: (
        "You are a research synthesis expert. From structured per-paper "
        "extractions and thematic clusters, derive cross-paper agreements, "
        "disagreements, trends, gaps, datasets, and methodologies."
    ),
    AgentRole.GAP_ANALYSIS: (
        "You are a research strategist. From cross-paper synthesis, identify "
        "prioritized research gaps, actionable opportunities, and "
        "underexplored areas."
    ),
    AgentRole.COVERAGE: (
        "You assess literature-search coverage. Judge whether the papers found "
        "so far answer the research query; when they do not, name the missing "
        "aspects and propose concise follow-up search queries targeting them."
    ),
    AgentRole.VERIFICATION: (
        "You verify claims against source material. Name the claims the given "
        "sources do not support, judging strictly from those sources."
    ),
}


def create_structured_agent(
    role: AgentRole,
    output_type: type[OutputT],
    llm_config=None,
    *,
    retries: int = 2,
    model: Model | None = None,
) -> Agent:
    """Create an agent whose output is validated against ``output_type``."""
    if model is None:
        resolved = AgentFactory(llm_config).config
        model = create_llm_provider(resolved).create_model(resolved)
    prompt = STRUCTURED_ROLE_PROMPTS.get(role) or ROLE_SYSTEM_PROMPTS[role]
    return Agent(
        model=model,
        system_prompt=prompt,
        output_type=output_type,
        retries=retries,
    )


async def run_structured(
    role: AgentRole,
    prompt: str,
    output_type: type[OutputT],
    llm_config=None,
    *,
    retries: int = 2,
    model: Model | None = None,
) -> OutputT:
    """Run a structured agent and return the validated output. Raises on failure."""
    agent = create_structured_agent(
        role,
        output_type,
        llm_config,
        retries=retries,
        model=model,
    )
    result = await agent.run(prompt)
    return result.output


async def try_run_structured(
    role: AgentRole,
    prompt: str,
    output_type: type[OutputT],
    llm_config=None,
    *,
    retries: int = 2,
    model: Model | None = None,
) -> OutputT | None:
    """Like :func:`run_structured`, but returns None on any failure."""
    try:
        return await run_structured(
            role,
            prompt,
            output_type,
            llm_config,
            retries=retries,
            model=model,
        )
    except Exception as exc:
        logger.warning("Structured %s call failed: %s", role.value, exc)
        return None
