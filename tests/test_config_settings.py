# -*- coding: utf-8 -*-
"""Tests for AppSettings YAML and environment override loading."""

import os
from pathlib import Path

import pytest
import yaml

from src.config.settings import AppSettings, load_yaml_config


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    default = {
        "llm": {"model": "default-model", "temperature": 0.1},
        "ranking": {"top_k": 10},
        "pipeline": {"debug": False},
    }
    with (config_dir / "default.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump(default, handle)

    with (config_dir / "models.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump({"model": "yaml-model", "temperature": 0.5}, handle)

    with (config_dir / "ranking.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump({"top_k": 20}, handle)

    return config_dir


class TestLoadYamlConfig:
    def test_merges_default_and_overlay_files(self, temp_config_dir: Path) -> None:
        data = load_yaml_config(temp_config_dir)

        assert data["llm"]["model"] == "yaml-model"
        assert data["llm"]["temperature"] == 0.5
        assert data["ranking"]["top_k"] == 20


class TestAppSettings:
    def test_loads_from_yaml(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pipenv loads .env into the process environment before pytest runs.
        for key in list(os.environ):
            if key.startswith("RA_"):
                monkeypatch.delenv(key, raising=False)

        settings = AppSettings.from_yaml(temp_config_dir)

        assert settings.llm.model == "yaml-model"
        assert settings.llm.temperature == 0.5
        assert settings.ranking.top_k == 20

    def test_env_overrides_yaml(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RA_LLM__MODEL", "env-model")
        monkeypatch.setenv("RA_RANKING__TOP_K", "99")

        settings = AppSettings.from_yaml(temp_config_dir)

        assert settings.llm.model == "env-model"
        assert settings.ranking.top_k == 99

    def test_constructor_overrides_env_and_yaml(
        self,
        temp_config_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("RA_LLM__MODEL", "env-model")

        settings = AppSettings.from_yaml(temp_config_dir, llm={"model": "init-model"})

        assert settings.llm.model == "init-model"

    def test_debug_enabled_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RA_DEBUG", "1")
        settings = AppSettings(pipeline={"debug": False})

        assert settings.debug_enabled is True

    def test_retrieval_providers_defaults(self) -> None:
        settings = AppSettings()

        assert "openalex" in settings.retrieval.providers
        assert settings.retrieval.providers["openalex"].enabled is True
