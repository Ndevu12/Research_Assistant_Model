# -*- coding: utf-8 -*-
"""OpenAI and OpenAI-compatible remote LLM provider."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .base import LLMProvider, normalize_openai_base_url, resolve_api_key

if TYPE_CHECKING:
    from ..config.settings import LLMConfig

_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com"
_OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"


def _resolve_openai_base_url(config: LLMConfig) -> str:
    base_url = config.base_url.rstrip("/") if config.base_url else ""
    if not base_url or base_url == _OLLAMA_DEFAULT_BASE_URL:
        return normalize_openai_base_url(_DEFAULT_OPENAI_BASE_URL)
    return normalize_openai_base_url(config.base_url)


class OpenAIProviderImpl(LLMProvider):
    """Provider for OpenAI and LM Studio-style OpenAI-compatible endpoints."""

    name = "openai"

    def create_model(self, config: LLMConfig) -> Model:
        base_url = _resolve_openai_base_url(config)
        api_key = resolve_api_key(config, "OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI provider requires an API key. "
                "Set RA_LLM__API_KEY or OPENAI_API_KEY."
            )
        provider = OpenAIProvider(base_url=base_url, api_key=api_key)
        return OpenAIChatModel(model_name=config.model, provider=provider)
