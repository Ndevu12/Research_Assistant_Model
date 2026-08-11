# -*- coding: utf-8 -*-
"""Embedding provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))


class EmbeddingProvider(ABC):
    """Interface for text embedding backends."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Return an array of shape ``(len(texts), dim)``."""

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Return cosine similarity between two vectors."""
        return cosine_similarity(a, b)

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text and return its vector."""
        return self.embed_texts([text])[0]
