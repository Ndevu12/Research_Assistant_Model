#!/usr/bin/env python3
"""Setup Ollama server and pull the model."""

import subprocess
import sys
import time


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


if __name__ == "__main__":
    setup_ollama()
