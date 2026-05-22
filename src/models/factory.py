# -*- coding: utf-8 -*-
"""LLM provider registry and agent factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from .anthropic import AnthropicProviderImpl
from .base import ROLE_SYSTEM_PROMPTS, AgentRole, LLMProvider
from .ollama import OllamaProvider
from .openai import OpenAIProviderImpl

if TYPE_CHECKING:
    from ..config.settings import LLMConfig

_PROVIDER_CLASSES: dict[str, type[LLMProvider]] = {
    OllamaProvider.name: OllamaProvider,
    OpenAIProviderImpl.name: OpenAIProviderImpl,
    AnthropicProviderImpl.name: AnthropicProviderImpl,
}


def register_llm_provider(provider_cls: type[LLMProvider]) -> type[LLMProvider]:
    """Register an LLM provider class by its ``name``."""
    _PROVIDER_CLASSES[provider_cls.name] = provider_cls
    return provider_cls


def get_llm_provider_class(name: str) -> type[LLMProvider]:
    """Return the provider class registered under ``name``."""
    normalized = name.strip().lower()
    try:
        return _PROVIDER_CLASSES[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(_PROVIDER_CLASSES))
        raise KeyError(f"Unknown LLM provider: {name}. Supported: {supported}") from exc


def create_llm_provider(config: LLMConfig | None = None) -> LLMProvider:
    """Instantiate the configured LLM provider."""
    resolved_config = _resolve_config(config)
    provider_cls = get_llm_provider_class(resolved_config.provider)
    return provider_cls()


class AgentFactory:
    """Create pydantic-ai agents for predefined research roles."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config

    @property
    def config(self) -> LLMConfig:
        return _resolve_config(self._config)

    def get_provider(self) -> LLMProvider:
        return create_llm_provider(self.config)

    def create_agent(
        self,
        role: AgentRole,
        *,
        system_prompt: str | None = None,
        config: LLMConfig | None = None,
    ) -> Agent:
        """Create an agent for a predefined role."""
        resolved_config = config or self.config
        provider = create_llm_provider(resolved_config)
        model = provider.create_model(resolved_config)
        prompt = system_prompt or ROLE_SYSTEM_PROMPTS[role]
        return Agent(model=model, system_prompt=prompt)

    def create_agent_with_prompt(
        self,
        system_prompt: str,
        config: LLMConfig | None = None,
    ) -> Agent:
        """Create an agent with a custom system prompt."""
        resolved_config = config or self.config
        provider = create_llm_provider(resolved_config)
        model = provider.create_model(resolved_config)
        return Agent(model=model, system_prompt=system_prompt)


def create_llm_agent(system_prompt: str, llm_config: LLMConfig | None = None) -> Agent:
    """Backward-compatible helper for modules that pass explicit prompts."""
    return AgentFactory(llm_config).create_agent_with_prompt(system_prompt, llm_config)


def _resolve_config(config: LLMConfig | None) -> LLMConfig:
    from ..config.model_selection import resolve_llm_model_name

    if config is not None:
        if config.model.strip().lower() == "auto":
            resolved_name = resolve_llm_model_name()
            return config.model_copy(update={"model": resolved_name})
        return config

    from ..config.settings import get_settings

    llm_config = get_settings().llm
    if llm_config.model.strip().lower() == "auto":
        resolved_name = resolve_llm_model_name()
        return llm_config.model_copy(update={"model": resolved_name})
    return llm_config
