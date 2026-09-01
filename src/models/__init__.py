# -*- coding: utf-8 -*-
"""LLM provider abstraction (not paper domain models)."""

from .base import ROLE_SYSTEM_PROMPTS, AgentRole, LLMProvider, normalize_openai_base_url
from .structured import (
    STRUCTURED_ROLE_PROMPTS,
    create_structured_agent,
    run_structured,
    try_run_structured,
)
from .factory import (
    AgentFactory,
    create_llm_agent,
    create_llm_provider,
    get_llm_provider_class,
    register_llm_provider,
)
from .ollama import OllamaProvider
from .openai import OpenAIProviderImpl
from .anthropic import AnthropicProviderImpl

__all__ = [
    "STRUCTURED_ROLE_PROMPTS",
    "create_structured_agent",
    "run_structured",
    "try_run_structured",
    "AgentFactory",
    "AgentRole",
    "AnthropicProviderImpl",
    "LLMProvider",
    "OllamaProvider",
    "OpenAIProviderImpl",
    "ROLE_SYSTEM_PROMPTS",
    "create_llm_agent",
    "create_llm_provider",
    "get_llm_provider_class",
    "normalize_openai_base_url",
    "register_llm_provider",
]
