# -*- coding: utf-8 -*-
"""LLM provider abstraction (not paper domain models)."""

from .base import ROLE_SYSTEM_PROMPTS, AgentRole, LLMProvider, normalize_openai_base_url
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
