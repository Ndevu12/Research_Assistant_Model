# -*- coding: utf-8 -*-
"""Tests for tri-state LLM feature resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config.resolve_llm_features import resolve_effective_settings
from src.config.settings import AppSettings


@pytest.fixture
def catalog_dir(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    catalog = {
        "auto_select": True,
        "fallback": "llama3.2:3b",
        "models": [
            {
                "name": "llama3.1:8b",
                "label": "Llama 3.1 8B",
                "min_ram_gb": 8,
                "recommended_ram_gb": 10,
                "disk_gb": 5,
                "priority": 100,
                "synthesis": {"llm_enabled": True, "max_llm_papers": 5},
            },
            {
                "name": "llama3.2:3b",
                "label": "Llama 3.2 3B",
                "min_ram_gb": 4,
                "recommended_ram_gb": 6,
                "disk_gb": 2.5,
                "priority": 50,
                "synthesis": {"llm_enabled": False, "max_llm_papers": 3},
            },
        ],
    }
    with (config_dir / "ollama_models.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump(catalog, handle)
    return config_dir


class TestResolveLlmFeatures:
    def test_llm_mode_auto_8b(self, catalog_dir: Path) -> None:
        settings = AppSettings(
            llm={"provider": "ollama", "model": "llama3.1:8b"},
            synthesis={"llm_mode": "auto"},
            query_expansion={"llm_mode": "auto"},
        )

        resolved = resolve_effective_settings(settings, config_dir=catalog_dir)

        assert resolved.synthesis.llm_enabled is True
        assert resolved.query_expansion.llm_enabled is True
        assert resolved.synthesis.max_llm_papers == 5

    def test_llm_mode_auto_3b(self, catalog_dir: Path) -> None:
        settings = AppSettings(
            llm={"provider": "ollama", "model": "llama3.2:3b"},
            synthesis={"llm_mode": "auto"},
            query_expansion={"llm_mode": "auto"},
        )

        resolved = resolve_effective_settings(settings, config_dir=catalog_dir)

        assert resolved.synthesis.llm_enabled is False
        assert resolved.query_expansion.llm_enabled is False
        assert resolved.synthesis.max_llm_papers == 3

    def test_llm_mode_on_off(self, catalog_dir: Path) -> None:
        off_settings = AppSettings(
            llm={"provider": "ollama", "model": "llama3.1:8b"},
            synthesis={"llm_mode": "off"},
            query_expansion={"llm_mode": "off"},
        )
        on_settings = AppSettings(
            llm={"provider": "ollama", "model": "llama3.2:3b"},
            synthesis={"llm_mode": "on"},
            query_expansion={"llm_mode": "on"},
        )

        off = resolve_effective_settings(off_settings, config_dir=catalog_dir)
        on = resolve_effective_settings(on_settings, config_dir=catalog_dir)

        assert off.synthesis.llm_enabled is False
        assert off.query_expansion.llm_enabled is False
        assert on.synthesis.llm_enabled is True
        assert on.query_expansion.llm_enabled is True

    def test_env_llm_enabled_overrides_mode(
        self,
        catalog_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = AppSettings(
            llm={"provider": "ollama", "model": "llama3.1:8b"},
            synthesis={"llm_mode": "off"},
            query_expansion={"llm_mode": "off"},
        )
        monkeypatch.setenv("RA_SYNTHESIS__LLM_ENABLED", "true")
        monkeypatch.setenv("RA_QUERY_EXPANSION__LLM_ENABLED", "true")

        resolved = resolve_effective_settings(settings, config_dir=catalog_dir)

        assert resolved.synthesis.llm_enabled is True
        assert resolved.query_expansion.llm_enabled is True

    def test_cloud_provider_auto_enables_llm(self, catalog_dir: Path) -> None:
        settings = AppSettings(
            llm={"provider": "openai", "model": "gpt-4o-mini"},
            synthesis={"llm_mode": "auto"},
            query_expansion={"llm_mode": "auto"},
        )

        resolved = resolve_effective_settings(settings, config_dir=catalog_dir)

        assert resolved.synthesis.llm_enabled is True
        assert resolved.query_expansion.llm_enabled is True

    def test_auto_resolves_model_name(self, catalog_dir: Path) -> None:
        settings = AppSettings.from_yaml(
            catalog_dir,
            llm={"provider": "ollama", "model": "llama3.1:8b"},
            synthesis={"llm_mode": "auto"},
        )

        resolved = resolve_effective_settings(settings, config_dir=catalog_dir)

        assert resolved.synthesis.llm_enabled is True
