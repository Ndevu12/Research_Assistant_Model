"""Setup utilities for AI Research Assistant."""

from .setup import install_python_deps
from .ollama import install_ollama, setup_ollama
from .health_check import check_python_deps, check_ollama_installed, check_ollama_running, check_model_available, print_report
from .manager import run_setup

__all__ = [
    "install_python_deps",
    "install_ollama",
    "setup_ollama",
    "check_python_deps",
    "check_ollama_installed",
    "check_ollama_running",
    "check_model_available",
    "print_report",
    "run_setup",
]
