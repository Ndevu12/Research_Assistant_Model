# -*- coding: utf-8 -*-
"""Tests for resource-aware Ollama model selection."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config.model_selection import (
    OllamaModelsCatalog,
    SystemResources,
    is_model_installed,
    list_installed_ollama_models,
    load_ollama_models_catalog,
    resolve_target_model,
    select_model_for_resources,
)


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


def _resources(
    *,
    available_ram_gb: float = 12.0,
    total_ram_gb: float = 16.0,
    free_disk_gb: float = 20.0,
    swap_pressure: float = 0.0,
) -> SystemResources:
    swap_total = 8.0 if swap_pressure > 0 else 0.0
    swap_used = swap_total * swap_pressure
    return SystemResources(
        total_ram_gb=total_ram_gb,
        available_ram_gb=available_ram_gb,
        free_disk_gb=free_disk_gb,
        swap_total_gb=swap_total,
        swap_used_gb=swap_used,
    )


class TestModelCatalog:
    def test_loads_catalog(self, catalog_dir: Path) -> None:
        catalog = load_ollama_models_catalog(catalog_dir)
        assert isinstance(catalog, OllamaModelsCatalog)
        assert catalog.fallback == "llama3.2:3b"
        assert len(catalog.models) == 2

    def test_model_by_name_is_case_insensitive(self, catalog_dir: Path) -> None:
        catalog = load_ollama_models_catalog(catalog_dir)
        spec = catalog.model_by_name("LLAMA3.1:8B")
        assert spec is not None
        assert spec.name == "llama3.1:8b"


class TestModelSelection:
    def test_selects_largest_model_when_resources_allow(self, catalog_dir: Path) -> None:
        catalog = load_ollama_models_catalog(catalog_dir)
        selection = select_model_for_resources(catalog, _resources(available_ram_gb=12.0))

        assert selection.model_name == "llama3.1:8b"
        assert selection.source == "auto"

    def test_falls_back_when_no_model_fits(self, catalog_dir: Path) -> None:
        catalog = load_ollama_models_catalog(catalog_dir)
        selection = select_model_for_resources(catalog, _resources(available_ram_gb=2.0))

        assert selection.model_name == "llama3.2:3b"
        assert selection.source == "fallback"

    def test_selects_smaller_model_when_only_it_fits(self, catalog_dir: Path) -> None:
        catalog = load_ollama_models_catalog(catalog_dir)
        selection = select_model_for_resources(catalog, _resources(available_ram_gb=5.0))

        assert selection.model_name == "llama3.2:3b"
        assert selection.source == "auto"

    def test_high_swap_pressure_requires_recommended_ram(self, catalog_dir: Path) -> None:
        catalog = load_ollama_models_catalog(catalog_dir)
        selection = select_model_for_resources(
            catalog,
            _resources(available_ram_gb=9.0, swap_pressure=0.9),
        )

        assert selection.model_name == "llama3.2:3b"

    def test_rejects_unsupported_explicit_model(self, catalog_dir: Path) -> None:
        with pytest.raises(ValueError, match="not supported"):
            resolve_target_model("mistral", config_dir=catalog_dir)

    def test_resolve_auto_uses_catalog(self, catalog_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RA_LLM__MODEL", raising=False)
        selection = resolve_target_model(
            "auto",
            config_dir=catalog_dir,
            resources=_resources(available_ram_gb=12.0),
        )
        assert selection.model_name == "llama3.1:8b"

    def test_resolve_configured_supported_model(self, catalog_dir: Path) -> None:
        selection = resolve_target_model(
            "llama3.2:3b",
            config_dir=catalog_dir,
            resources=_resources(available_ram_gb=12.0),
        )
        assert selection.model_name == "llama3.2:3b"
        assert selection.source == "cli"

    def test_env_override_beats_auto(self, catalog_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RA_LLM__MODEL", "llama3.1:8b")
        selection = resolve_target_model(
            config_dir=catalog_dir,
            resources=_resources(available_ram_gb=5.0),
        )
        assert selection.model_name == "llama3.1:8b"
        assert selection.source == "env"
        assert "RA_LLM__MODEL override" in selection.reason

    def test_configured_model_request_detects_env_source(
        self,
        catalog_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from src.config.model_selection import _configured_model_request

        monkeypatch.setenv("RA_LLM__MODEL", "llama3.2:3b")
        model, source = _configured_model_request(catalog_dir)
        assert model == "llama3.2:3b"
        assert source == "env"


class TestOllamaListParsing:
    def test_list_installed_models_parses_name_column(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Result:
            stdout = "NAME           ID\nllama3.1:8b    abc\nllama3.2:3b    def\n"
            returncode = 0

        monkeypatch.setattr(
            "src.config.model_selection.subprocess.run",
            lambda *args, **kwargs: Result(),
        )

        assert list_installed_ollama_models() == {"llama3.1:8b", "llama3.2:3b"}
        assert is_model_installed("llama3.1:8b") is True
        assert is_model_installed("llama3.1") is False
