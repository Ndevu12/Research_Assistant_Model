# -*- coding: utf-8 -*-
"""Embedding provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class EmbeddingProvider(ABC):
    """Interface for text embedding backends."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Return an array of shape ``(len(texts), dim)``."""

    @abstractmethod
    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Return cosine similarity between two vectors."""

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text and return its vector."""
        return self.embed_texts([text])[0]
