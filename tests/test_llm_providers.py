# -*- coding: utf-8 -*-
"""Tests for LLM provider abstraction and agent factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.config.settings import LLMConfig
from src.models import (
    AgentFactory,
    AgentRole,
    OllamaProvider,
    OpenAIProviderImpl,
    create_llm_agent,
    create_llm_provider,
    get_llm_provider_class,
    normalize_openai_base_url,
)
from src.models.anthropic import AnthropicProviderImpl


class TestNormalizeOpenAIBaseUrl:
    def test_appends_v1_suffix(self) -> None:
        assert normalize_openai_base_url("http://localhost:11434") == "http://localhost:11434/v1"

    def test_preserves_existing_v1_suffix(self) -> None:
        assert normalize_openai_base_url("http://localhost:11434/v1") == "http://localhost:11434/v1"

    def test_strips_trailing_slash(self) -> None:
        assert normalize_openai_base_url("http://localhost:11434/") == "http://localhost:11434/v1"


class TestLLMProviderRegistry:
    def test_default_provider_is_ollama(self) -> None:
        provider = create_llm_provider(LLMConfig())

        assert isinstance(provider, OllamaProvider)

    def test_get_provider_class_openai(self) -> None:
        provider_cls = get_llm_provider_class("openai")

        assert provider_cls is OpenAIProviderImpl

    def test_get_provider_class_anthropic(self) -> None:
        provider_cls = get_llm_provider_class("anthropic")

        assert provider_cls is AnthropicProviderImpl

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(KeyError, match="Unknown LLM provider"):
            get_llm_provider_class("unknown-backend")


class TestOllamaProvider:
    @patch("src.models.ollama.OpenAIChatModel")
    @patch("src.models.ollama.OpenAIProvider")
    def test_create_model_uses_openai_compatible_endpoint(
        self,
        mock_openai_provider: MagicMock,
        mock_openai_model: MagicMock,
    ) -> None:
        config = LLMConfig(
            provider="ollama",
            model="llama3.2",
            base_url="http://localhost:11434",
        )
        provider = OllamaProvider()

        provider.create_model(config)

        mock_openai_provider.assert_called_once_with(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
        )
        mock_openai_model.assert_called_once_with(
            model_name="llama3.2",
            provider=mock_openai_provider.return_value,
        )


class TestOpenAIProvider:
    @patch("src.models.openai.OpenAIChatModel")
    @patch("src.models.openai.OpenAIProvider")
    def test_create_model_requires_api_key(
        self,
        mock_openai_provider: MagicMock,
        mock_openai_model: MagicMock,
    ) -> None:
        provider = OpenAIProviderImpl()
        config = LLMConfig(provider="openai", model="gpt-4o-mini", api_key="test-key")

        provider.create_model(config)

        mock_openai_provider.assert_called_once_with(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
        )

    def test_create_model_raises_without_api_key(self) -> None:
        provider = OpenAIProviderImpl()
        config = LLMConfig(provider="openai", model="gpt-4o-mini", api_key=None)

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="requires an API key"):
                provider.create_model(config)


class TestAgentFactory:
    @patch("src.models.factory.Agent")
    @patch("src.models.factory.create_llm_provider")
    def test_create_agent_uses_role_prompt(
        self,
        mock_create_provider: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        mock_provider = MagicMock()
        mock_model = MagicMock()
        mock_provider.create_model.return_value = mock_model
        mock_create_provider.return_value = mock_provider

        config = LLMConfig(provider="ollama", model="llama3.2")
        factory = AgentFactory(config)
        agent = factory.create_agent(AgentRole.EXTRACTION)

        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["model"] is mock_model
        assert "paper_id" in call_kwargs["system_prompt"]
        assert agent is mock_agent_cls.return_value

    @patch("src.models.factory.AgentFactory.create_agent_with_prompt")
    def test_create_llm_agent_compat_helper(self, mock_create: MagicMock) -> None:
        mock_create.return_value = MagicMock()
        config = LLMConfig()

        agent = create_llm_agent("Custom prompt", config)

        mock_create.assert_called_once_with("Custom prompt", config)
        assert agent is mock_create.return_value

    @patch("src.models.factory.Agent")
    @patch("src.models.factory.create_llm_provider")
    def test_analysis_agent_role_prompt(
        self,
        mock_create_provider: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        mock_provider = MagicMock()
        mock_provider.create_model.return_value = MagicMock()
        mock_create_provider.return_value = mock_provider

        factory = AgentFactory(LLMConfig())
        factory.create_agent(AgentRole.ANALYSIS)

        call_kwargs = mock_agent_cls.call_args.kwargs
        assert '"papers"' in call_kwargs["system_prompt"]
