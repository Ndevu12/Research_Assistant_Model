#!/usr/bin/env python3
"""Install Python dependencies for AI Research Assistant."""

import importlib.util
import subprocess
import sys

REQUIRED_PACKAGES = ["pydantic-ai", "aiohttp", "pydantic"]


def install_python_deps() -> None:
    """Install missing Python packages via pip."""
    missing = []
    for pkg in REQUIRED_PACKAGES:
        mod = pkg.replace("-", "_").split("[")[0]
        if importlib.util.find_spec(mod) is None:
            missing.append(pkg)

    if missing:
        print(f"Installing missing packages: {missing}")
        subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=True)
        print("Python dependencies installed successfully.")
    else:
        print("All Python dependencies already satisfied.")


if __name__ == "__main__":
    install_python_deps()
