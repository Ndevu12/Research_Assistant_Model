# -*- coding: utf-8 -*-
"""Resource-aware Ollama model selection from config/ollama_models.yaml."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from .settings import _default_config_dir


class OllamaModelSynthesisHints(BaseModel):
    llm_enabled: bool = False
    max_llm_papers: int = 3


class OllamaModelSpec(BaseModel):
    name: str
    label: str = ""
    min_ram_gb: float
    recommended_ram_gb: float | None = None
    disk_gb: float
    priority: int = 0
    synthesis: OllamaModelSynthesisHints = Field(default_factory=OllamaModelSynthesisHints)


class OllamaModelsCatalog(BaseModel):
    auto_select: bool = True
    fallback: str = "llama3.2:3b"
    models: list[OllamaModelSpec] = Field(default_factory=list)

    def model_by_name(self, name: str) -> OllamaModelSpec | None:
        normalized = name.strip().lower()
        for spec in self.models:
            if spec.name.lower() == normalized:
                return spec
        return None

    def supported_names(self) -> list[str]:
        return [spec.name for spec in self.models]


@dataclass(frozen=True)
class SystemResources:
    total_ram_gb: float
    available_ram_gb: float
    free_disk_gb: float
    swap_total_gb: float
    swap_used_gb: float

    @property
    def swap_pressure(self) -> float:
        if self.swap_total_gb <= 0:
            return 0.0
        return self.swap_used_gb / self.swap_total_gb


@dataclass(frozen=True)
class ModelSelectionResult:
    model_name: str
    spec: OllamaModelSpec | None
    source: str
    reason: str
    resources: SystemResources


_AUTO_VALUES = frozenset({"auto", ""})


def load_ollama_models_catalog(config_dir: Path | None = None) -> OllamaModelsCatalog:
    """Load the Ollama model catalog from ``config/ollama_models.yaml``."""
    directory = config_dir or _default_config_dir()
    path = directory / "ollama_models.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"Ollama model catalog not found at {path}. "
            "Create config/ollama_models.yaml with supported models."
        )

    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    return OllamaModelsCatalog.model_validate(raw)


def _read_linux_meminfo() -> tuple[float, float, float, float]:
    total_kb = 0.0
    available_kb = 0.0
    swap_total_kb = 0.0
    swap_free_kb = 0.0

    with Path("/proc/meminfo").open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("MemTotal:"):
                total_kb = float(line.split()[1])
            elif line.startswith("MemAvailable:"):
                available_kb = float(line.split()[1])
            elif line.startswith("SwapTotal:"):
                swap_total_kb = float(line.split()[1])
            elif line.startswith("SwapFree:"):
                swap_free_kb = float(line.split()[1])

    total_gb = total_kb / (1024**2)
    available_gb = available_kb / (1024**2)
    swap_total_gb = swap_total_kb / (1024**2)
    swap_used_gb = max(0.0, (swap_total_kb - swap_free_kb) / (1024**2))
    return total_gb, available_gb, swap_total_gb, swap_used_gb


def _read_darwin_memory() -> tuple[float, float]:
    total_bytes = int(
        subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
    )
    vm_stat = subprocess.check_output(["vm_stat"], text=True)
    page_size = 4096
    free_pages = 0.0
    inactive_pages = 0.0
    for line in vm_stat.splitlines():
        if "page size of" in line:
            page_size = int(line.split()[-2])
        elif line.strip().startswith("Pages free"):
            free_pages = float(line.split(":")[-1].strip().rstrip("."))
        elif line.strip().startswith("Pages inactive"):
            inactive_pages = float(line.split(":")[-1].strip().rstrip("."))

    available_bytes = (free_pages + inactive_pages) * page_size
    return total_bytes / (1024**3), available_bytes / (1024**3)


def detect_system_resources(
    *,
    disk_path: Path | None = None,
) -> SystemResources:
    """Detect RAM, swap pressure, and free disk for model selection."""
    system = platform.system()
    swap_total_gb = 0.0
    swap_used_gb = 0.0

    if system == "Linux":
        total_gb, available_gb, swap_total_gb, swap_used_gb = _read_linux_meminfo()
    elif system == "Darwin":
        total_gb, available_gb = _read_darwin_memory()
    else:
        total_gb = 8.0
        available_gb = 4.0

    target = disk_path or _ollama_home()
    target.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(target)
    free_disk_gb = disk.free / (1024**3)

    return SystemResources(
        total_ram_gb=total_gb,
        available_ram_gb=available_gb,
        free_disk_gb=free_disk_gb,
        swap_total_gb=swap_total_gb,
        swap_used_gb=swap_used_gb,
    )


def _ollama_home() -> Path:
    return Path(os.environ.get("OLLAMA_MODELS", Path.home() / ".ollama"))


def _model_fits(spec: OllamaModelSpec, resources: SystemResources) -> tuple[bool, str]:
    if resources.free_disk_gb < spec.disk_gb:
        return (
            False,
            f"needs {spec.disk_gb:.1f} GB disk, {resources.free_disk_gb:.1f} GB free",
        )

    required_ram = spec.min_ram_gb
    if resources.swap_pressure >= 0.85:
        required_ram = spec.recommended_ram_gb or spec.min_ram_gb

    if resources.available_ram_gb < required_ram:
        return (
            False,
            (
                f"needs {required_ram:.1f} GB RAM "
                f"({resources.available_ram_gb:.1f} GB available"
                f"{', high swap pressure' if resources.swap_pressure >= 0.85 else ''})"
            ),
        )

    return True, "requirements met"


def select_model_for_resources(
    catalog: OllamaModelsCatalog,
    resources: SystemResources,
) -> ModelSelectionResult:
    """Pick the highest-priority catalog model that fits available resources."""
    ordered = sorted(catalog.models, key=lambda spec: spec.priority, reverse=True)
    for spec in ordered:
        fits, detail = _model_fits(spec, resources)
        if fits:
            return ModelSelectionResult(
                model_name=spec.name,
                spec=spec,
                source="auto",
                reason=f"Selected {spec.label or spec.name}: {detail}",
                resources=resources,
            )

    fallback_spec = catalog.model_by_name(catalog.fallback)
    if fallback_spec is None and catalog.models:
        fallback_spec = min(catalog.models, key=lambda spec: spec.min_ram_gb)
        catalog = catalog.model_copy(update={"fallback": fallback_spec.name})

    fallback_name = catalog.fallback
    return ModelSelectionResult(
        model_name=fallback_name,
        spec=catalog.model_by_name(fallback_name),
        source="fallback",
        reason=(
            "No catalog model fit available resources; "
            f"using fallback '{fallback_name}'"
        ),
        resources=resources,
    )


def _configured_model_request(config_dir: Path | None = None) -> tuple[str, str]:
    """Return the configured model request and its source label.

    Precedence (highest to lowest):
    1. ``RA_LLM__MODEL`` in the process environment
    2. ``RA_LLM__MODEL`` in the project ``.env`` file
    3. ``llm.model`` from merged YAML config
    """
    from .settings import AppSettings

    directory = config_dir or _default_config_dir()
    yaml_settings = AppSettings.from_yaml(directory)
    yaml_model = yaml_settings.llm.model.strip() or "auto"

    if config_dir is not None:
        settings = AppSettings.from_yaml(config_dir)
    else:
        settings = AppSettings()

    model = settings.llm.model.strip() or "auto"

    if os.environ.get("RA_LLM__MODEL", "").strip():
        return model, "env"

    if not config_dir and model != yaml_model:
        return model, "env"

    if model.lower() in _AUTO_VALUES:
        return model, "auto"
    return model, "yaml"


def resolve_target_model(
    model_request: str | None = None,
    *,
    config_dir: Path | None = None,
    resources: SystemResources | None = None,
) -> ModelSelectionResult:
    """Resolve the Ollama model to install or run.

    Precedence: explicit ``model_request`` (CLI) > ``RA_LLM__MODEL`` (env/.env) >
    YAML ``llm.model`` > resource-based auto selection.
    """
    catalog = load_ollama_models_catalog(config_dir)
    detected = resources or detect_system_resources()

    if model_request is not None:
        requested = model_request.strip()
        request_source = "cli"
    else:
        requested, request_source = _configured_model_request(config_dir)

    if requested.lower() in _AUTO_VALUES:
        if not catalog.auto_select:
            requested = catalog.fallback
            spec = catalog.model_by_name(requested)
            if spec is None:
                raise ValueError(
                    f"Fallback model '{catalog.fallback}' is not listed in ollama_models.yaml"
                )
            return ModelSelectionResult(
                model_name=requested,
                spec=spec,
                source="fallback",
                reason="auto_select disabled in catalog; using fallback",
                resources=detected,
            )
        return select_model_for_resources(catalog, detected)

    spec = catalog.model_by_name(requested)
    if spec is None:
        supported = ", ".join(catalog.supported_names())
        raise ValueError(
            f"Model '{requested}' is not supported. "
            f"Supported models: {supported}"
        )

    fits, detail = _model_fits(spec, detected)
    if request_source == "env":
        prefix = f"Using RA_LLM__MODEL override '{requested}'"
    elif request_source == "yaml":
        prefix = f"Using llm.model from config '{requested}'"
    else:
        prefix = f"Using configured model '{requested}'"

    if fits:
        reason = f"{prefix}: {detail}"
    else:
        reason = (
            f"{prefix}, but it may not run well ({detail}). "
            "Consider a smaller model or freeing memory."
        )

    return ModelSelectionResult(
        model_name=requested,
        spec=spec,
        source=request_source,
        reason=reason,
        resources=detected,
    )


def resolve_llm_model_name(
    model_request: str | None = None,
    *,
    config_dir: Path | None = None,
) -> str:
    """Return a concrete Ollama model name for runtime LLM calls."""
    return resolve_target_model(model_request, config_dir=config_dir).model_name


def list_installed_ollama_models() -> set[str]:
    """Return model names reported by ``ollama list``."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return set()

    names: set[str] = set()
    for line in result.stdout.splitlines()[1:]:
        if not line.strip():
            continue
        names.add(line.split()[0])
    return names


def is_model_installed(model_name: str) -> bool:
    """Check whether ``model_name`` is installed in the local Ollama registry."""
    return model_name in list_installed_ollama_models()


def synthesis_hints_for_model(model_name: str, config_dir: Path | None = None) -> dict[str, Any]:
    """Return synthesis tuning hints for a supported model, if defined."""
    catalog = load_ollama_models_catalog(config_dir)
    spec = catalog.model_by_name(model_name)
    if spec is None:
        return {}
    return spec.synthesis.model_dump()
