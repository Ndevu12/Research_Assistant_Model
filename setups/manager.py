#!/usr/bin/env python3
"""Simple setup orchestrator for AI Research Assistant."""

import sys
from pathlib import Path

# Add parent directory to path to import logging system
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_system import logger

# Import setup modules - use absolute imports when called from outside
try:
    from .setup import install_python_deps
    from .ollama import install_ollama, setup_ollama
except ImportError:
    # Fallback for when imported as a module from sys.path
    from setup import install_python_deps
    from ollama import install_ollama, setup_ollama


def run_setup(model_name: str | None = None) -> bool:
    """Run the complete setup process.

    Args:
        model_name: Ollama model to use, or None to auto-select from config.

    Returns:
        bool: True if all steps succeeded, False otherwise
    """
    logger.info("=== AI Research Assistant Setup ===")

    steps = [
        ("Python Dependencies", install_python_deps, []),
        ("Ollama Installation", install_ollama, []),
        ("Ollama Model Setup", setup_ollama, [model_name]),
    ]

    failed_steps = []
    selected_model = None

    for step_name, step_func, args in steps:
        try:
            logger.info(f"\nStep: {step_name}")
            result = step_func(*args)
            if step_name == "Ollama Model Setup" and result is not None:
                selected_model = result.model_name
            logger.info(f"✓ {step_name} completed successfully")
        except Exception as e:
            logger.error(f"✗ {step_name} failed: {e}")
            failed_steps.append((step_name, str(e)))

    logger.info("\n=== Setup Summary ===")
    completed = len(steps) - len(failed_steps)
    logger.info(f"Completed: {completed}/{len(steps)}")

    if selected_model:
        logger.info(f"Configured Ollama model: {selected_model}")

    if failed_steps:
        logger.warning(f"\nFailed steps ({len(failed_steps)}):")
        for step_name, error in failed_steps:
            logger.error(f"  ✗ {step_name}: {error}")
        return False

    logger.info("\n✓ All setup steps completed successfully!")
    logger.info("\nTo run the assistant:")
    logger.info("  pipenv run python -m src")
    logger.info("  OR")
    logger.info("  pipenv shell  # then run python -m src")
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Setup AI Research Assistant")
    parser.add_argument(
        "--model",
        default=None,
        help="Ollama model to install (default: auto-select from config/ollama_models.yaml)",
    )

    args = parser.parse_args()

    try:
        success = run_setup(model_name=args.model)
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Setup failed with exception: {e}")
        sys.exit(1)
