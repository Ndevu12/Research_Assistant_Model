# -*- coding: utf-8 -*-
"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _skip_environment_setup() -> Iterator[None]:
    """Keep tests hermetic: never run the real Ollama install/health-check path.

    ``src.__main__.main`` calls ``ensure_setup`` which can install Ollama and
    pull models. No test exercises that path intentionally, so it is stubbed
    out globally to keep the suite fast and network-independent.
    """
    with patch("src.__main__.ensure_setup", return_value=True):
        yield
