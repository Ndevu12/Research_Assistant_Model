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


def setup_ollama(model_name: str = "llama3.2:3b") -> None:
    """Start Ollama server if not running, then pull the model if needed."""
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

    # Check if model exists - check for full model name with tag
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    model_exists = any(model_name in line for line in result.stdout.splitlines())
    
    if not model_exists:
        logger.info(f"Model '{model_name}' not found. Pulling...")
        # Retry pull up to 3 times
        for attempt in range(3):
            try:
                subprocess.run(["ollama", "pull", model_name], check=True)
                logger.info("Model pull complete.")
                break
            except subprocess.CalledProcessError as e:
                if attempt == 2:
                    raise RuntimeError(f"Failed to pull model after 3 attempts: {e}")
                logger.warning(f"Pull attempt {attempt + 1} failed. Retrying in 5 seconds...")
                time.sleep(5)
    else:
        logger.info(f"Model '{model_name}' already available.")


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
        default="llama3.2:3b",
        help="Model name for setup command (default: llama3.2:3b)"
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
