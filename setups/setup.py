#!/usr/bin/env python3
"""Install Python dependencies for AI Research Assistant using pipenv."""

import subprocess
import sys
from pathlib import Path

# Add parent directory to path to import logging system
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_system import logger


def install_python_deps() -> None:
    """Install Python dependencies via pipenv."""
    logger.info("Checking/Installing Python dependencies via pipenv...")
    
    # Check if pipenv is installed, install if not
    try:
        subprocess.run(["pipenv", "--version"], check=True, capture_output=True)
        logger.info("pipenv is already installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("pipenv not found. Installing pipenv...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pipenv"], check=True)
        logger.info("pipenv installed successfully.")
    
    # Install dependencies using pipenv (creates venv if needed)
    logger.info("Installing dependencies...")
    subprocess.run(["pipenv", "install", "--dev"], check=True)
    logger.info("Python dependencies installed successfully via pipenv.")


if __name__ == "__main__":
    try:
        install_python_deps()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to install Python dependencies: {e}")
        sys.exit(1)
