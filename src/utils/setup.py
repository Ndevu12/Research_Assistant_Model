#!/usr/bin/env python3
"""Install Python dependencies for AI Research Assistant using pipenv."""

import subprocess
import sys


def install_python_deps() -> None:
    """Install Python dependencies via pipenv."""
    print("Checking/Installing Python dependencies via pipenv...")
    
    # Check if pipenv is installed, install if not
    try:
        subprocess.run(["pipenv", "--version"], check=True, capture_output=True)
        print("pipenv is already installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("pipenv not found. Installing pipenv...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pipenv"], check=True)
        print("pipenv installed successfully.")
    
    # Install dependencies using pipenv (creates venv if needed)
    print("Installing dependencies...")
    subprocess.run(["pipenv", "install", "--dev"], check=True)
    print("Python dependencies installed successfully via pipenv.")
