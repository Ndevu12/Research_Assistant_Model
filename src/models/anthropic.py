# -*- coding: utf-8 -*-
"""Anthropic LLM provider."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from .base import LLMProvider, resolve_api_key

if TYPE_CHECKING:
    from ..config.settings import LLMConfig


class AnthropicProviderImpl(LLMProvider):
    """Provider for Anthropic Claude models."""

    name = "anthropic"

    def create_model(self, config: LLMConfig) -> Model:
        api_key = resolve_api_key(config, "ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Anthropic provider requires an API key. "
                "Set RA_LLM__API_KEY or ANTHROPIC_API_KEY."
            )
        provider_kwargs: dict[str, str] = {"api_key": api_key}
        if config.base_url:
            provider_kwargs["base_url"] = config.base_url.rstrip("/")
        provider = AnthropicProvider(**provider_kwargs)
        return AnthropicModel(model_name=config.model, provider=provider)
