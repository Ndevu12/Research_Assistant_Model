#!/usr/bin/env python3
"""Install Ollama in an OS-aware manner."""

import platform
import shutil
import subprocess
import sys


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


if __name__ == "__main__":
    install_ollama()
