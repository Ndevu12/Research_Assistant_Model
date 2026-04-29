#!/usr/bin/env python3
"""Health check utilities to verify setup completion."""

import shutil
import subprocess
import sys
from pathlib import Path

# Add parent directory to path to import logging system
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_system import logger


def check_python_deps() -> tuple[bool, str]:
    """Check if Python dependencies are installed.
    
    Checks if:
    1. pipenv is available as a CLI tool
    2. Project dependencies are installed (by checking for key packages)
    """
    # Check if pipenv CLI is available
    if not shutil.which("pipenv"):
        return False, "pipenv not installed"
    
    # Check if key project dependencies are available
    try:
        import aiohttp  # noqa - key dependency from Pipfile
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


def check_model_available(model_name: str = "llama3.2:3b") -> tuple[bool, str]:
    """Check if the specified model is available."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if model_name in result.stdout:
            return True, f"Model '{model_name}' is available"
        return False, f"Model '{model_name}' not found"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False, "Cannot check model availability"


def print_report(model_name: str = "llama3.2:3b") -> bool:
    """Print health check report and return overall status."""
    checks = {
        "Python Dependencies": check_python_deps(),
        "Ollama Installed": check_ollama_installed(),
        "Ollama Running": check_ollama_running(),
        f"Model '{model_name}'": check_model_available(model_name),
    }
    
    print("\n=== Setup Health Check ===")
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
        default="llama3.2:3b",
        help="Model name to check (default: llama3.2:3b)"
    )
    
    args = parser.parse_args()
    
    try:
        success = print_report(args.model)
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        sys.exit(1)
