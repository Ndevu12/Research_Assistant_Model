#!/usr/bin/env python3
"""Run all setup steps for AI Research Assistant."""

import subprocess
import sys


def run_setup() -> None:
    """Run all auto-setup steps."""
    print("=== AI Research Assistant Auto-Setup ===")

    # Install Python dependencies
    print("\nStep 1: Installing Python dependencies...")
    subprocess.run([sys.executable, "-m", "src.utils.setup"], check=True)

    # Install Ollama
    print("\nStep 2: Installing Ollama...")
    subprocess.run([sys.executable, "-m", "src.utils.ollama", "install"], check=True)

    # Setup Ollama model
    print("\nStep 3: Setting up Ollama model...")
    subprocess.run([sys.executable, "-m", "src.utils.ollama", "setup"], check=True)

    print("\n=== Setup Complete ===")
    print("\nTo run the assistant:")
    print("  pipenv run python -m src")
    print("  OR")
    print("  pipenv shell  # then run python -m src")
