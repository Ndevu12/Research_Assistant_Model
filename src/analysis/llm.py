# -*- coding: utf-8 -*-
"""Analysis agent configuration for the analysis module."""

from ..models import AgentFactory, AgentRole

_factory = AgentFactory()
analysis_agent = _factory.create_agent(AgentRole.ANALYSIS)
