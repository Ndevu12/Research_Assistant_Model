# -*- coding: utf-8 -*-
"""Resolve effective LLM feature flags from tri-state mode and runtime context."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from ..utils.logging_system import logger
from .model_selection import resolve_llm_model_name, synthesis_hints_for_model
from .settings import AppSettings, SynthesisConfig, _default_config_dir

LlmMode = Literal["auto", "on", "off"]
_CLOUD_LLM_PROVIDERS = frozenset({"openai", "anthropic"})
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})


def _env_llm_enabled_override(section: str) -> bool | None:
    """Return explicit ``RA_{SECTION}__LLM_ENABLED`` override when set."""
    env_key = f"RA_{section.upper()}__LLM_ENABLED"
    raw = os.environ.get(env_key, "").strip().lower()
    if raw in _TRUTHY:
        return True
    if raw in _FALSY:
        return False
    return None


def _normalize_mode(mode: str) -> LlmMode:
    normalized = mode.strip().lower()
    if normalized in {"auto", "on", "off"}:
        return normalized  # type: ignore[return-value]
    logger.warning("Unknown llm_mode %r; treating as 'off'", mode)
    return "off"


def _resolve_mode(
    *,
    section: str,
    configured_mode: str,
    env_override: bool | None,
) -> LlmMode:
    if env_override is not None:
        return "on" if env_override else "off"
    return _normalize_mode(configured_mode)


def _resolve_auto_llm_enabled(
    *,
    provider: str,
    model_name: str,
    config_dir: Path | None,
) -> bool:
    if provider in _CLOUD_LLM_PROVIDERS:
        return True

    if provider != "ollama":
        return False

    hints = synthesis_hints_for_model(model_name, config_dir)
    return bool(hints.get("llm_enabled", False))


def _resolve_llm_enabled(
    *,
    section: str,
    configured_mode: str,
    provider: str,
    model_name: str,
    config_dir: Path | None,
) -> bool:
    env_override = _env_llm_enabled_override(section)
    mode = _resolve_mode(
        section=section,
        configured_mode=configured_mode,
        env_override=env_override,
    )

    if mode == "on":
        return True
    if mode == "off":
        return False

    return _resolve_auto_llm_enabled(
        provider=provider,
        model_name=model_name,
        config_dir=config_dir,
    )


def _resolve_ollama_model_name(settings: AppSettings, config_dir: Path | None) -> str:
    model_request = settings.llm.model.strip()
    if model_request.lower() not in {"", "auto"}:
        return model_request

    try:
        return resolve_llm_model_name(config_dir=config_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Could not resolve Ollama model for LLM auto mode: %s", exc)
        return model_request or "auto"


def _apply_ollama_synthesis_hints(
    synthesis: SynthesisConfig,
    *,
    provider: str,
    model_name: str,
    config_dir: Path | None,
) -> SynthesisConfig:
    if provider != "ollama":
        return synthesis

    hints = synthesis_hints_for_model(model_name, config_dir)
    if not hints:
        return synthesis

    updates: dict[str, object] = {}
    if "max_llm_papers" in hints:
        updates["max_llm_papers"] = hints["max_llm_papers"]
    if not updates:
        return synthesis

    return synthesis.model_copy(update=updates)


def resolve_effective_settings(
    settings: AppSettings,
    config_dir: Path | None = None,
) -> AppSettings:
    """Resolve ``llm_enabled`` and Ollama synthesis hints once at pipeline start.

    Precedence for each feature (synthesis, query expansion):
    1. ``RA_{SECTION}__LLM_ENABLED`` environment variable (backward compatible)
    2. ``llm_mode: on|off`` from settings / ``RA_{SECTION}__LLM_MODE``
    3. ``llm_mode: auto`` — cloud providers on; Ollama uses ``synthesis_hints_for_model``
    """
    directory = config_dir or _default_config_dir()
    provider = settings.llm.provider.strip().lower()
    model_name = _resolve_ollama_model_name(settings, directory)

    synthesis_enabled = _resolve_llm_enabled(
        section="synthesis",
        configured_mode=settings.synthesis.llm_mode,
        provider=provider,
        model_name=model_name,
        config_dir=directory,
    )
    expansion_enabled = _resolve_llm_enabled(
        section="query_expansion",
        configured_mode=settings.query_expansion.llm_mode,
        provider=provider,
        model_name=model_name,
        config_dir=directory,
    )

    synthesis = settings.synthesis.model_copy(update={"llm_enabled": synthesis_enabled})
    synthesis = _apply_ollama_synthesis_hints(
        synthesis,
        provider=provider,
        model_name=model_name,
        config_dir=directory,
    )
    query_expansion = settings.query_expansion.model_copy(
        update={"llm_enabled": expansion_enabled},
    )

    logger.info(
        "Resolved LLM features (provider=%s, model=%s): synthesis=%s, query_expansion=%s",
        provider,
        model_name,
        synthesis_enabled,
        expansion_enabled,
    )
    if synthesis_enabled and synthesis.max_llm_papers != settings.synthesis.max_llm_papers:
        logger.info(
            "Applied Ollama synthesis hints: max_llm_papers=%d",
            synthesis.max_llm_papers,
        )

    return settings.model_copy(
        update={
            "synthesis": synthesis,
            "query_expansion": query_expansion,
        },
    )
