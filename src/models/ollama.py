# -*- coding: utf-8 -*-
"""Ollama LLM provider (OpenAI-compatible API)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .base import LLMProvider, normalize_openai_base_url, resolve_api_key

if TYPE_CHECKING:
    from ..config.settings import LLMConfig


class OllamaProvider(LLMProvider):
    """Default provider targeting a local Ollama server."""

    name = "ollama"

    def create_model(self, config: LLMConfig) -> Model:
        base_url = normalize_openai_base_url(config.base_url)
        api_key = resolve_api_key(config, "OLLAMA_API_KEY", default="ollama")
        provider = OpenAIProvider(base_url=base_url, api_key=api_key)
        return OpenAIChatModel(model_name=config.model, provider=provider)
