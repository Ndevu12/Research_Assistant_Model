#!/usr/bin/env python3
"""Run all setup steps for AI Research Assistant."""

import subprocess
import sys


def run_setup() -> None:
    """Run all auto-setup steps."""
    print("=== AI Research Assistant Auto-Setup ===")

    # Install Python dependencies
    print("\nStep 1: Installing Python dependencies...")
    subprocess.run([sys.executable, "setup/install_deps.py"], check=True)

    # Install Ollama
    print("\nStep 2: Installing Ollama...")
    subprocess.run([sys.executable, "setup/install_ollama.py"], check=True)

    # Setup Ollama model
    print("\nStep 3: Setting up Ollama model...")
    subprocess.run([sys.executable, "setup/setup_ollama_model.py"], check=True)

    print("\n=== Setup Complete ===")


if __name__ == "__main__":
    run_setup()
