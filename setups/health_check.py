#!/usr/bin/env python3
"""Health check utilities to verify setup completion."""

import shutil
import subprocess
import sys
from pathlib import Path

# Add parent directory to path to import logging system
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.model_selection import (
    is_model_installed,
    resolve_target_model,
)
from src.utils.logging_system import logger


def check_embedding_deps() -> tuple[bool, str]:
    """Check if embedding dependencies are installed."""
    try:
        import sentence_transformers  # noqa: F401
        return True, "sentence-transformers installed"
    except ImportError:
        return False, "sentence-transformers not installed (run: pipenv install)"


def check_python_deps() -> tuple[bool, str]:
    """Check if Python dependencies are installed."""
    if not shutil.which("pipenv"):
        return False, "pipenv not installed"

    try:
        import aiohttp  # noqa: F401
        return True, "Python dependencies installed"
    except ImportError:
        return False, "Python dependencies not fully installed (missing aiohttp)"


def check_ollama_installed() -> tuple[bool, str]:
    """Check if Ollama binary is installed."""
    if shutil.which("ollama"):
        return True, "Ollama binary found"
    return False, "Ollama binary not found"


def check_ollama_running() -> tuple[bool, str]:
    """Check if Ollama server is running."""
    try:
        subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True, "Ollama server is running"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False, "Ollama server is not running"


def check_model_available(model_name: str | None = None) -> tuple[bool, str]:
    """Check if the resolved or specified model is available."""
    try:
        selection = resolve_target_model(model_name)
    except (FileNotFoundError, ValueError) as exc:
        return False, str(exc)

    if is_model_installed(selection.model_name):
        return True, f"Model '{selection.model_name}' is available ({selection.source})"
    return False, f"Model '{selection.model_name}' not installed ({selection.reason})"


def print_report(model_name: str | None = None) -> bool:
    """Print health check report and return overall status."""
    try:
        selection = resolve_target_model(model_name)
        model_label = selection.model_name
        model_detail = selection.reason
    except (FileNotFoundError, ValueError) as exc:
        selection = None
        model_label = model_name or "auto"
        model_detail = str(exc)

    checks = {
        "Python Dependencies": check_python_deps(),
        "Embedding Dependencies": check_embedding_deps(),
        "Ollama Installed": check_ollama_installed(),
        "Ollama Running": check_ollama_running(),
    }

    if selection is not None:
        checks[f"Model '{model_label}'"] = check_model_available(model_name)

    print("\n=== Setup Health Check ===")
    if selection is not None:
        source_label = {
            "env": "env override (RA_LLM__MODEL)",
            "yaml": "config (llm.model)",
            "cli": "CLI (--model)",
            "auto": "auto-selected",
            "fallback": "fallback",
        }.get(selection.source, selection.source)
        print(f"Target model: {model_label} ({source_label})")
        print(f"Selection: {model_detail}")
        print(
            f"Resources: {selection.resources.available_ram_gb:.1f} GB RAM available, "
            f"{selection.resources.free_disk_gb:.1f} GB disk free"
        )

    all_passed = True
    for check_name, (passed, message) in checks.items():
        status = "✓" if passed else "✗"
        print(f"{status} {check_name}: {message}")
        if not passed:
            all_passed = False

    print()
    return all_passed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Health check for setup")
    parser.add_argument(
        "--model",
        default=None,
        help="Model name to check (default: resolve from config/ollama_models.yaml)",
    )

    args = parser.parse_args()

    try:
        success = print_report(args.model)
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        sys.exit(1)
