# -*- coding: utf-8 -*-
"""Analysis agent configuration for the analysis module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import AgentFactory, AgentRole

if TYPE_CHECKING:
    from pydantic_ai import Agent

_cached_agent: Agent | None = None


def get_analysis_agent() -> Agent:
    """Return the shared analysis agent, creating it on first use.

    Lazily constructed so importing the analysis package has no side effects
    (no settings resolution, no model creation).
    """
    global _cached_agent
    if _cached_agent is None:
        _cached_agent = AgentFactory().create_agent(AgentRole.ANALYSIS)
    return _cached_agent


def __getattr__(name: str) -> Any:
    if name == "analysis_agent":
        return get_analysis_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
