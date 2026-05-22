# -*- coding: utf-8 -*-
"""Embedding providers and caching."""

from .base import EmbeddingProvider
from .cache import EmbeddingCache
from .sentence_transformers import (
    SentenceTransformerEmbeddingProvider,
    create_embedding_provider,
)


def try_create_embedding_provider(
    config=None,
) -> EmbeddingProvider | None:
    """Return the default embedding provider, or None if dependencies are missing."""
    try:
        return create_embedding_provider(config)
    except ImportError:
        return None


__all__ = [
    "EmbeddingCache",
    "EmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    "create_embedding_provider",
    "try_create_embedding_provider",
]
