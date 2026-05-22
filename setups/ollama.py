#!/usr/bin/env python3
"""Install Ollama in an OS-aware manner."""

import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Add parent directory to path to import logging system
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.model_selection import (
    ModelSelectionResult,
    is_model_installed,
    resolve_target_model,
)
from src.utils.logging_system import logger


def install_ollama() -> None:
    """Install Ollama using the appropriate method for the current OS."""
    if shutil.which("ollama"):
        logger.info("Ollama already installed.")
        return

    system = platform.system()
    logger.info(f"Ollama not found. Installing for {system}...")

    if system == "Linux":
        try:
            with open("/etc/os-release") as f:
                os_release = f.read().lower()
        except FileNotFoundError:
            os_release = ""

        if "arch" in os_release or "manjaro" in os_release:
            if shutil.which("yay"):
                logger.info("Using yay to install ollama...")
                subprocess.run(["yay", "-S", "--noconfirm", "ollama"], check=True)
            elif shutil.which("pacman"):
                logger.info("Using pacman to install ollama...")
                subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "ollama"], check=True)
            else:
                raise RuntimeError("No AUR helper found. Install ollama manually: https://ollama.com")
        elif "ubuntu" in os_release or "debian" in os_release:
            logger.info("Using official install script for Ubuntu/Debian...")
            result = subprocess.run(
                ["curl", "-fsSL", "https://ollama.com/install.sh"],
                capture_output=True, check=True
            )
            subprocess.run(["sh"], input=result.stdout, check=True)
        else:
            logger.info("Using generic Linux install script...")
            result = subprocess.run(
                ["curl", "-fsSL", "https://ollama.com/install.sh"],
                capture_output=True, check=True
            )
            subprocess.run(["sh"], input=result.stdout, check=True)

    elif system == "Darwin":
        if shutil.which("brew"):
            logger.info("Using Homebrew to install ollama...")
            subprocess.run(["brew", "install", "ollama"], check=True)
        else:
            raise RuntimeError("Homebrew not found. Install it from https://brew.sh then run: brew install ollama")
    else:
        raise RuntimeError(f"Unsupported OS: {system}. Install Ollama manually from https://ollama.com/download")

    logger.info("Ollama installed successfully.")


def _ensure_ollama_server() -> None:
    try:
        subprocess.run(["ollama", "list"], capture_output=True, check=True, timeout=5)
        logger.info("Ollama server already running.")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        logger.info("Starting Ollama server...")
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(5)


def _log_selection(selection: ModelSelectionResult) -> None:
    logger.info(selection.reason)
    logger.info(
        "System resources: %.1f GB RAM available / %.1f GB total, "
        "%.1f GB disk free, swap pressure %.0f%%",
        selection.resources.available_ram_gb,
        selection.resources.total_ram_gb,
        selection.resources.free_disk_gb,
        selection.resources.swap_pressure * 100,
    )
    if selection.spec and selection.spec.synthesis.llm_enabled:
        logger.info(
            "Tip: enable LLM synthesis for this model with RA_SYNTHESIS__LLM_ENABLED=true"
        )


def setup_ollama(model_name: str | None = None) -> ModelSelectionResult:
    """Start Ollama server if needed, resolve model, and pull if missing."""
    selection = resolve_target_model(model_name)
    _log_selection(selection)

    _ensure_ollama_server()

    if is_model_installed(selection.model_name):
        logger.info(f"Model '{selection.model_name}' already available.")
        return selection

    logger.info(f"Model '{selection.model_name}' not found. Pulling...")
    for attempt in range(3):
        try:
            subprocess.run(["ollama", "pull", selection.model_name], check=True)
            logger.info("Model pull complete.")
            return selection
        except subprocess.CalledProcessError as exc:
            if attempt == 2:
                raise RuntimeError(
                    f"Failed to pull model '{selection.model_name}' after 3 attempts: {exc}"
                ) from exc
            logger.warning(f"Pull attempt {attempt + 1} failed. Retrying in 5 seconds...")
            time.sleep(5)

    return selection


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ollama setup utility")
    parser.add_argument(
        "command",
        choices=["install", "setup"],
        help="Command to run: 'install' to install Ollama, 'setup' to configure model"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Ollama model to install (default: auto-select from config/ollama_models.yaml)",
    )

    args = parser.parse_args()

    try:
        if args.command == "install":
            install_ollama()
        elif args.command == "setup":
            setup_ollama(args.model)
        sys.exit(0)
    except Exception as e:
        logger.error(f"Ollama setup failed: {e}")
        sys.exit(1)
