# -*- coding: utf-8 -*-
"""Optional HTTP API scaffold for the research pipeline.

Requires ``fastapi`` and ``uvicorn`` (not core dependencies). Install with::

    pipenv install fastapi uvicorn

Run locally::

    uvicorn src.api.app:create_app --factory --reload
"""

from .app import create_app

__all__ = ["create_app"]
