#!/usr/bin/env python3
"""Install Ollama in an OS-aware manner."""

import platform
import shutil
import subprocess
import sys
import time


def install_ollama() -> None:
    """Install Ollama using the appropriate method for the current OS."""
    if shutil.which("ollama"):
        print("Ollama already installed.")
        return

    system = platform.system()
    print(f"Ollama not found. Installing for {system}...")

    if system == "Linux":
        try:
            with open("/etc/os-release") as f:
                os_release = f.read().lower()
        except FileNotFoundError:
            os_release = ""

        if "arch" in os_release or "manjaro" in os_release:
            if shutil.which("yay"):
                print("Using yay to install ollama...")
                subprocess.run(["yay", "-S", "--noconfirm", "ollama"], check=True)
            elif shutil.which("pacman"):
                print("Using pacman to install ollama...")
                subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "ollama"], check=True)
            else:
                raise RuntimeError("No AUR helper found. Install ollama manually: https://ollama.com")
        elif "ubuntu" in os_release or "debian" in os_release:
            print("Using official install script for Ubuntu/Debian...")
            result = subprocess.run(
                ["curl", "-fsSL", "https://ollama.com/install.sh"],
                capture_output=True, check=True
            )
            subprocess.run(["sh"], input=result.stdout, check=True)
        else:
            print("Using generic Linux install script...")
            result = subprocess.run(
                ["curl", "-fsSL", "https://ollama.com/install.sh"],
                capture_output=True, check=True
            )
            subprocess.run(["sh"], input=result.stdout, check=True)

    elif system == "Darwin":
        if shutil.which("brew"):
            print("Using Homebrew to install ollama...")
            subprocess.run(["brew", "install", "ollama"], check=True)
        else:
            raise RuntimeError("Homebrew not found. Install it from https://brew.sh then run: brew install ollama")
    else:
        raise RuntimeError(f"Unsupported OS: {system}. Install Ollama manually from https://ollama.com/download")

    print("Ollama installed successfully.")


def setup_ollama(model_name: str = "llama3.2:3b") -> None:
    """Start Ollama server if not running, then pull the model if needed."""
    try:
        subprocess.run(["ollama", "list"], capture_output=True, check=True, timeout=5)
        print("Ollama server already running.")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        print("Starting Ollama server...")
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
        print(f"Model '{model_name}' not found. Pulling...")
        # Retry pull up to 3 times
        for attempt in range(3):
            try:
                subprocess.run(["ollama", "pull", model_name], check=True)
                print("Model pull complete.")
                break
            except subprocess.CalledProcessError as e:
                if attempt == 2:
                    raise RuntimeError(f"Failed to pull model after 3 attempts: {e}")
                print(f"Pull attempt {attempt + 1} failed. Retrying in 5 seconds...")
                time.sleep(5)
    else:
        print(f"Model '{model_name}' already available.")
